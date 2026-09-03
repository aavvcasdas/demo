from typing import Tuple, Dict, Optional, Union
import pandas as pd
from sklearn.model_selection import train_test_split
import torch
from torch.utils.data import DataLoader, Dataset
from PIL import Image
import torchvision.transforms as transforms
from torchvision.models import vit_b_16
from sklearn.metrics import f1_score, accuracy_score, precision_score, recall_score, roc_auc_score, \
    classification_report
import numpy as np


def main():
    # 读取CSV
    df = pd.read_csv('../../archive/ODIR-5K/ODIR-5K/data_copy_utf-8.csv')

    # 图像路径和标签提取
    img_paths = df['filepath'].values
    labels = df['target'].apply(lambda x: list(map(int, x.strip('[]').split(',')))).values

    # 划分数据集
    train_paths, test_paths, train_labels, test_labels = train_test_split(img_paths, labels, test_size=0.2, random_state=42)
    train_paths, val_paths, train_labels, val_labels = train_test_split(train_paths, train_labels, test_size=0.2, random_state=42)

    # ViT处理
    vit_transform = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.RandomHorizontalFlip(),
        transforms.RandomRotation(10),
        transforms.ColorJitter(brightness=0.1, contrast=0.1),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])

    # 实例Dataset
    train_dataset = OcularDataset(train_paths, train_labels, vit_transform)
    val_dataset = OcularDataset(val_paths, val_labels, vit_transform)
    test_dataset = OcularDataset(test_paths, test_labels, vit_transform)

    # Loader
    batch_size = 64

    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True, num_workers=4)
    val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False, num_workers=4)
    test_loader = DataLoader(test_dataset, batch_size=batch_size, shuffle=False, num_workers=4)

    # 加载预训练ViT，修改输出层
    model = vit_b_16(pretrained=True)
    model.heads.head = torch.nn.Linear(model.heads.head.in_features, 8)

    # 训练与验证流程
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    model = model.to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-4)
    criterion = torch.nn.BCEWithLogitsLoss()
    scaler = torch.cuda.amp.GradScaler()
    num_epochs = 120

    best_val_loss = float('inf')
    patience = 10
    counter = 0

    for epoch in range(num_epochs):
        # 训练
        train_loss, train_metrics = train_epoch(model, train_loader, criterion, optimizer, device, scaler)

        # 验证
        val_loss, val_metrics = validate_epoch(model, val_loader, criterion, device)

        # 结果打印
        print(f"Epoch {epoch+1} / {num_epochs}")
        print(f"Train Loss: {train_loss:.4f} | Train F1: {train_metrics['f1']:.4f}")
        print(f"Val Loss: {val_loss:.4f} | Val F1: {val_metrics['f1']:.4f}")
        print(f"Precision: {val_metrics['precision']:.4f} | Recall: {val_metrics['recall']:.4f}")
        print('-'*60)

        if val_loss < best_val_loss:
            best_val_loss = val_loss
            counter = 0
            # 保存最佳模型
            torch.save({
                "model_state": model.state_dict(),
                "label_mapping": ['N', 'D', 'G', 'C', 'A', 'H', 'M', 'O']
            }, "best_model.pth")
        else:
            counter += 1
            if counter >= patience:
                print(f"早停：验证损失连续{patience}次没有改善")
                break

    #测试
    class_names = ['N', 'D', 'G', 'C', 'A', 'H', 'M', 'O']

    test_loss, test_metrics, test_predictions = final_epoch(model, test_loader, criterion, device, class_names, return_predictions=True, threshold=0.4)

    # 最终输出
    print("\n=== 测试结果汇总 ===")
    print(f"平均测试损失: {test_loss:.4f}")
    print(f"宏平均F1: {test_metrics['f1_macro']:.4f}")
    print(f"ROC-AUC: {test_metrics['roc_auc']:.4f}")

    # 保存详细预测结果
    test_predictions.to_csv('Detail_predictions.csv', index=False)

    # 可视化报告
    print("\n=== 分类详情报告 ===")
    print(classification_report(
        test_predictions['true_labels'].apply(lambda x: set(x.split(','))),
        test_predictions['pred_labels'].apply(lambda x: set(x.split(','))),
        target_names=class_names
    ))

    # 保存
    torch.save({
        "model_state": model.state_dict(),
        "label_mapping": ['N', 'D', 'G', 'C', 'A', 'H', 'M', 'O']
    }, "ocular_ViT_model.pth")

    # 加载方式
    """
    checkpoint = torch.load("ocular_ViT_model.pth")
    model.load_state_dict(checkpoint["model_state"])
    labels = checkpoint["label_mapping"]
    """


class OcularDataset(Dataset):
    def __init__(self, img_paths, labels, transform=None):
        self.img_paths = img_paths
        self.labels = labels
        self.transform = transform

    def __len__(self):
        return len(self.img_paths)

    def __getitem__(self, index):
        image = Image.open(self.img_paths[index]).convert('RGB')
        label = torch.tensor(self.labels[index], dtype=torch.float32)

        if self.transform:
            image = self.transform(image)

        return image, label


# 训练流程
def train_epoch(
        model: torch.nn.Module,
        train_loader: DataLoader,
        criterion: torch.nn.Module,
        optimizer: torch.optim.Optimizer,
        device: torch.device,
        scaler: torch.cuda.amp.GradScaler = None
) -> Tuple[float, Dict[str, float]]:
    """
    :param model: 待训练模型
    :param train_loader: 训练数据加载器
    :param criterion: 损失函数
    :param optimizer: 优化器
    :param device: 训练设备 (GPU/CPU)
    :param scaler: 混合精度梯度缩放器 (可选)
    :return: 一个元组, 包含平均训练损失 (float) 和包含训练指标的字典 (accuracy, precision, recall, f1)
    """
    model.train()
    total_loss = 0.0
    all_preds = []
    all_labels = []

    for batch_index, (inputs, labels) in enumerate(train_loader):
        # 数据转移至设备
        inputs, labels = inputs.to(device), labels.to(device)

        # 梯度清零
        optimizer.zero_grad()

        #混合精度前向传播
        with torch.cuda.amp.autocast(enabled=(scaler is not None)):
            outputs = model(inputs)
            loss = criterion(outputs, labels)

        #反向传播和优化
        if scaler:
            scaler.scale(loss).backward()
            scaler.step(optimizer)
            scaler.update()
        else:
            loss.backward()
            optimizer.step()

        # 记录损失和预测
        total_loss += loss.item()
        probs = torch.sigmoid(outputs)
        preds = (probs > 0.5).float()
        all_preds.append(preds.cpu().detach().numpy())
        all_labels.append(labels.cpu().detach().numpy())

    # 合并batch结果
    all_preds = np.concatenate(all_preds)
    all_labels = np.concatenate(all_labels)

    # 计算指标
    avg_loss = total_loss / len(train_loader)
    metrics = {
        "loss": avg_loss,
        "accuracy": accuracy_score(all_labels, all_preds),
        "precision": precision_score(all_labels, all_preds, average="micro"),
        "recall": recall_score(all_labels, all_preds, average="micro"),
        "f1": f1_score(all_labels, all_preds, average="micro"),
    }

    return avg_loss, metrics


# 验证流程
def validate_epoch(
        model: torch.nn.Module,
        val_loader: DataLoader,
        criterion: torch.nn.Module,
        device: torch.device,
) -> Tuple[float, Dict[str, float]]:
    """
    :param model: 待验证模型
    :param val_loader: 验证数据加载器
    :param criterion: 损失函数
    :param device: 验证设备 (GPU/CPU)
    :return: 一个元组, 包含评价训练损失 (float) 和 包含验证指标的字典(accuracy, precision, recall, f1)
    """
    model.eval()
    total_loss = 0.0
    all_preds = []
    all_labels = []

    with torch.no_grad():
        for inputs, labels in val_loader:
            inputs, labels = inputs.to(device), labels.to(device)

            #前向传播
            outputs = model(inputs)
            loss = criterion(outputs, labels)

            # 记录结果
            total_loss += loss.item()
            probs = torch.sigmoid(outputs)
            preds = (probs > 0.5).float()
            all_preds.append(preds.cpu().numpy())
            all_labels.append(labels.cpu().numpy())

    # 合并结果并计算
    all_preds = np.concatenate(all_preds)
    all_labels = np.concatenate(all_labels)

    avg_loss = total_loss / len(val_loader)
    metrics = {
        "loss": avg_loss,
        "accuracy": accuracy_score(all_labels, all_preds),
        "precision": precision_score(all_labels, all_preds, average="micro"),
        "recall": recall_score(all_labels, all_preds, average="micro"),
        "f1": f1_score(all_labels, all_preds, average="micro"),
    }

    return avg_loss, metrics


# 测试流程
def final_epoch(
        model: torch.nn.Module,
        test_loader: DataLoader,
        criterion: torch.nn.Module,
        device: torch.device,
        class_names: Optional[list] = None,
        return_predictions: bool = False,
        threshold: float = 0.4,
) -> Union[Tuple[float, Dict[str, float]], Tuple[float, Dict[str, float], pd.DataFrame]]:
    """
    :param model: 训练好的模型
    :param test_loader: 测试数据加载器
    :param criterion: 损失函数
    :param device: 计算设备 (GPU/CPU)
    :param class_names: 类别名称列表 (用于生成分类报告)
    :param return_predictions: 是否返回预测结果DataFrame
    :param threshold: 分类阈值
    :return: 一个联合类型，根据 return_Predictions 参数的值返回不同的结果：
             - 如果 return_Predictions 为 False，返回一个包含两个元素的元组：
               - 第一个元素是平均测试损失，类型为 float。
               - 第二个元素是包含评估指标的字典，键为指标名称（如 'accuracy', 'precision', 'recall', 'f1' 等），值为对应的指标值，类型为 Dict[str, float]。
             - 如果 return_Predictions 为 True，返回一个包含三个元素的元组：
               - 第一个元素是平均测试损失，类型为 float。
               - 第二个元素是包含评估指标的字典，键为指标名称（如 'accuracy', 'precision', 'recall', 'f1' 等），值为对应的指标值，类型为 Dict[str, float]。
               - 第三个元素是包含预测结果的 DataFrame，类型为 pd.DataFrame。
    """
    model.eval()
    total_loss = 0.0
    all_probs = []
    all_preds = []
    all_labels = []
    # all_ids = []

    with torch.no_grad():
        for batch in test_loader:
            inputs, labels, ids = batch
            inputs, labels = inputs.to(device), labels.to(device)

            # 前向传播
            outputs = model(inputs)
            loss = criterion(outputs, labels)

            # 记录结果
            total_loss += loss.item()
            probs = torch.sigmoid(outputs).cpu().numpy()
            preds = (probs > threshold).astype(int)

            all_probs.append(probs)
            all_preds.append(preds)
            all_labels.append(labels.cpu().numpy())
            # all_ids.extend(ids)

    # 合并结果
    all_probs = np.concatenate(all_probs)
    all_preds = np.concatenate(all_preds)
    all_labels = np.concatenate(all_labels)

    # 计算核心指标
    avg_loss = total_loss / len(test_loader)
    metrics = {
        "loss": avg_loss,
        "accuracy": accuracy_score(all_labels, all_preds),
        "precision": precision_score(all_labels, all_preds, average="micro"),
        "recall": recall_score(all_labels, all_preds, average="micro"),
        "f1": f1_score(all_labels, all_preds, average="micro"),
        "roc_auc": roc_auc_score(all_labels, all_probs, average="macro"),
    }

    # 添加分类报告细节
    if class_names is not None:
        report = classification_report(
            all_labels,
            all_preds,
            target_names=class_names,
            output_dict=True,
            zero_division=0
        )
        metrics.update({
            "precision_macro": report['macro avg']['precision'],
            "recall_macro": report['macro avg']['recall'],
            "f1_macro": report['macro avg']['f1-score'],
        })

    # 构建预测结果DataFrame
    predictions_df = None
    if return_predictions:
        df_data = []
        for index, (prob, pred, label) in enumerate(zip(all_probs, all_preds, all_labels)):
            record = {
                # "sample_id": all_ids[index],
                "true_labels": ','.join([class_names[i] for i, v in enumerate(label) if v == 1]),
                "pred_labels": ','.join([class_names[i] for i, v in enumerate(pred) if v == 1])
            }
            # 类别概率
            for i, cls in enumerate(class_names):
                record[f"prob_{cls}"] = prob[i]
            df_data.append(record)

        predictions_df = pd.DataFrame(df_data)

    # 返回结果
    if return_predictions:
        return avg_loss, metrics, predictions_df
    return avg_loss, metrics


if __name__ == "__main__":
    main()