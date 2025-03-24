# method2.py
from typing import Tuple, Dict, Optional, Union, List
import os
import yaml
import pandas as pd
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, Dataset
from PIL import Image
import torchvision.transforms as transforms
from sklearn.metrics import f1_score, precision_score, recall_score
import matplotlib.pyplot as plt
from tqdm import tqdm

# 定义YOLO模型的基础组件
class ConvBlock(nn.Module):
    def __init__(self, in_channels, out_channels, kernel_size=3, stride=1, padding=1):
        super().__init__()
        self.conv = nn.Conv2d(in_channels, out_channels, kernel_size, stride, padding, bias=False)
        self.bn = nn.BatchNorm2d(out_channels)
        self.act = nn.SiLU()
    
    def forward(self, x):
        return self.act(self.bn(self.conv(x)))

class ResidualBlock(nn.Module):
    def __init__(self, channels):
        super().__init__()
        self.block = nn.Sequential(
            ConvBlock(channels, channels // 2, kernel_size=1, padding=0),
            ConvBlock(channels // 2, channels, kernel_size=3, padding=1)
        )
    
    def forward(self, x):
        return x + self.block(x)

# 定义YOLO Neck (特征金字塔)
class YOLONeck(nn.Module):
    def __init__(self, in_channels, mid_channels):
        super().__init__()
        self.conv1 = ConvBlock(in_channels, mid_channels, kernel_size=1, padding=0)
        self.conv2 = ConvBlock(mid_channels, mid_channels*2, kernel_size=3, padding=1)
        self.conv3 = ConvBlock(mid_channels*2, mid_channels, kernel_size=1, padding=0)
        self.conv4 = ConvBlock(mid_channels, mid_channels*2, kernel_size=3, padding=1)
        self.conv5 = ConvBlock(mid_channels*2, mid_channels, kernel_size=1, padding=0)
    
    def forward(self, x):
        x = self.conv1(x)
        x = self.conv2(x)
        x = self.conv3(x)
        x = self.conv4(x)
        x = self.conv5(x)
        return x

# 定义YOLO检测头
class YOLOHead(nn.Module):
    def __init__(self, in_channels, num_classes):
        super().__init__()
        # 每个边界框预测5+num_classes个值:
        # 4个边界框坐标(x,y,w,h), 1个objectness分数, num_classes个类别分数
        self.num_outputs = 5 + num_classes
        self.head = nn.Conv2d(in_channels, 3 * self.num_outputs, kernel_size=1)
    
    def forward(self, x):
        return self.head(x)

# 自定义YOLO模型
class YOLOModel(nn.Module):
    def __init__(self, num_classes):
        super().__init__()
        
        # 主干网络
        self.backbone = nn.Sequential(
            # 初始卷积块
            ConvBlock(3, 32, kernel_size=3, stride=1),
            ConvBlock(32, 64, kernel_size=3, stride=2),
            
            # 第一个残差块组
            ResidualBlock(64),
            ConvBlock(64, 128, kernel_size=3, stride=2),
            
            # 第二个残差块组
            ResidualBlock(128),
            ResidualBlock(128),
            ConvBlock(128, 256, kernel_size=3, stride=2),
            
            # 第三个残差块组
            ResidualBlock(256),
            ResidualBlock(256),
            ResidualBlock(256),
            ConvBlock(256, 512, kernel_size=3, stride=2),
            
            # 第四个残差块组
            ResidualBlock(512),
            ResidualBlock(512),
            ResidualBlock(512),
        )
        
        # 颈部
        self.neck = YOLONeck(512, 256)
        
        # 检测头
        self.head = YOLOHead(256, num_classes)
        
        self.num_classes = num_classes
    
    def forward(self, x):
        # 特征提取
        x = self.backbone(x)
        
        # 特征处理
        x = self.neck(x)
        
        # 检测头
        x = self.head(x)
        
        # 重塑输出以分离不同的预测
        batch_size, _, grid_h, grid_w = x.shape
        
        # 重塑为 [batch, 3, grid_h, grid_w, num_outputs]
        x = x.view(batch_size, 3, -1, grid_h, grid_w).permute(0, 1, 3, 4, 2)
        
        return x

# YOLO数据集类
class YOLODataset(Dataset):
    def __init__(self, root_dir, set_name, img_size=640, transform=None):
        self.root_dir = root_dir
        self.img_size = img_size
        self.set_name = set_name
        self.transform = transform
        
        # 读取图像和标签文件路径
        self.img_dir = os.path.join(root_dir, 'images', set_name)
        self.label_dir = os.path.join(root_dir, 'labels', set_name)
        
        self.img_files = [f for f in os.listdir(self.img_dir) if f.endswith(('.jpg', '.jpeg', '.png'))]
        
        # 读取类别名称
        with open(os.path.join(root_dir, 'classes.txt'), 'r') as f:
            self.class_names = [line.strip() for line in f.readlines()]
    
    def __len__(self):
        return len(self.img_files)
    
    def __getitem__(self, idx):
        img_path = os.path.join(self.img_dir, self.img_files[idx])
        img = Image.open(img_path).convert('RGB')
        
        # 处理图像尺寸
        orig_w, orig_h = img.size
        
        # 构建标签路径
        label_path = os.path.join(
            self.label_dir, 
            os.path.splitext(self.img_files[idx])[0] + '.txt'
        )
        
        # 读取标签
        targets = []
        if os.path.exists(label_path):
            with open(label_path, 'r') as f:
                for line in f.readlines():
                    data = line.strip().split()
                    cls_id = int(data[0])
                    # 中心x,y,宽,高的归一化值
                    x_center, y_center = float(data[1]), float(data[2])
                    width, height = float(data[3]), float(data[4])
                    
                    # 转换为[class_id, x_center, y_center, width, height]格式
                    targets.append([cls_id, x_center, y_center, width, height])
        
        targets = np.array(targets, dtype=np.float32)
        
        # 应用转换
        if self.transform:
            img = self.transform(img)
        
        return img, targets, self.img_files[idx]

# 损失函数计算
class YOLOLoss(nn.Module):
    def __init__(self, num_classes):
        super().__init__()
        self.num_classes = num_classes
        self.bce = nn.BCEWithLogitsLoss(reduction='none')
        self.mse = nn.MSELoss(reduction='none')
        
        # 损失权重
        self.lambda_coord = 5.0
        self.lambda_obj = 1.0
        self.lambda_noobj = 0.5
        self.lambda_class = 1.0
    
    def forward(self, predictions, targets, anchors):
        # 这里简化了损失计算，实际YOLO损失更复杂
        # 包括边界框坐标、置信度和类别概率的损失
        obj_loss = 0
        box_loss = 0
        class_loss = 0
        
        # 简化的损失计算
        # 实际实现中会处理网格、锚框和IoU计算
        
        return {
            'loss': obj_loss + box_loss + class_loss,
            'box_loss': box_loss,
            'obj_loss': obj_loss,
            'class_loss': class_loss
        }

def main():
    # 数据集配置
    data_dir = './odir_yolo'
    
    # 读取配置文件
    with open(os.path.join(data_dir, 'odir.yaml'), 'r') as f:
        cfg = yaml.safe_load(f)
    
    num_classes = cfg['nc']
    class_names = cfg['names']
    
    # 数据转换
    transform = transforms.Compose([
        transforms.Resize((640, 640)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])
    
    # 创建数据集和数据加载器
    train_dataset = YOLODataset(data_dir, 'train', transform=transform)
    val_dataset = YOLODataset(data_dir, 'val', transform=transform)
    test_dataset = YOLODataset(data_dir, 'test', transform=transform)
    
    batch_size = 16  # 根据GPU内存调整
    
    train_loader = DataLoader(
        train_dataset, batch_size=batch_size, shuffle=True, 
        num_workers=4, pin_memory=True, collate_fn=collate_fn
    )
    val_loader = DataLoader(
        val_dataset, batch_size=batch_size, shuffle=False, 
        num_workers=4, pin_memory=True, collate_fn=collate_fn
    )
    test_loader = DataLoader(
        test_dataset, batch_size=batch_size, shuffle=False, 
        num_workers=4, pin_memory=True, collate_fn=collate_fn
    )
    
    # 创建模型
    model = YOLOModel(num_classes)
    
    # 训练设备
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    model = model.to(device)
    
    # 优化器
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-4)
    
    # 学习率调度器
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
        optimizer, mode='min', factor=0.1, patience=5, verbose=True
    )
    
    # 训练参数
    num_epochs = 100
    best_map = 0
    
    # 定义锚框 (通常通过聚类计算)
    anchors = torch.tensor([
        [[10, 13], [16, 30], [33, 23]],  # 小尺寸锚框
        [[30, 61], [62, 45], [59, 119]],  # 中尺寸锚框
        [[116, 90], [156, 198], [373, 326]]  # 大尺寸锚框
    ]).to(device)
    
    # 损失函数
    criterion = YOLOLoss(num_classes)
    
    # 训练循环
    for epoch in range(num_epochs):
        # 训练
        model.train()
        train_loss = 0
        
        progress_bar = tqdm(train_loader, desc=f"Epoch {epoch+1}/{num_epochs}")
        for imgs, targets, _ in progress_bar:
            # 将数据移到设备
            imgs = imgs.to(device)
            targets = [t.to(device) if len(t) > 0 else t for t in targets]
            
            # 梯度清零
            optimizer.zero_grad()
            
            # 前向传播
            outputs = model(imgs)
            
            # 计算损失
            loss_dict = criterion(outputs, targets, anchors)
            loss = loss_dict['loss']
            
            # 反向传播和优化
            loss.backward()
            optimizer.step()
            
            # 更新进度条
            train_loss += loss.item()
            progress_bar.set_postfix(loss=f"{train_loss/(progress_bar.n+1):.4f}")
        
        # 计算平均训练损失
        train_loss /= len(train_loader)
        
        # 验证
        model.eval()
        val_loss = 0
        
        with torch.no_grad():
            for imgs, targets, _ in tqdm(val_loader, desc="Validating"):
                imgs = imgs.to(device)
                targets = [t.to(device) if len(t) > 0 else t for t in targets]
                
                outputs = model(imgs)
                loss_dict = criterion(outputs, targets, anchors)
                val_loss += loss_dict['loss'].item()
        
        val_loss /= len(val_loader)
        
        # 学习率调度
        scheduler.step(val_loss)
        
        # 打印结果
        print(f"Epoch {epoch+1}/{num_epochs}, Train Loss: {train_loss:.4f}, Val Loss: {val_loss:.4f}")
        
        # 保存最佳模型
        if val_loss < best_map:
            best_map = val_loss
            torch.save(model.state_dict(), "best_yolo_model.pt")
            print(f"保存最佳模型，验证损失: {val_loss:.4f}")
    
    # 加载最佳模型进行测试
    model.load_state_dict(torch.load("best_yolo_model.pt"))
    model.eval()
    
    # 测试
    test_results = []
    
    with torch.no_grad():
        for imgs, targets, img_names in tqdm(test_loader, desc="Testing"):
            imgs = imgs.to(device)
            
            # 前向传播
            outputs = model(imgs)
            
            # 处理预测结果
            batch_detections = process_predictions(outputs, anchors, num_classes)
            
            # 收集结果
            for i, detections in enumerate(batch_detections):
                img_name = img_names[i]
                img_targets = targets[i]
                
                # 将检测结果添加到列表
                for det in detections:
                    x1, y1, x2, y2, conf, cls_id = det
                    test_results.append({
                        'image': img_name,
                        'class': class_names[int(cls_id)],
                        'confidence': float(conf),
                        'bbox': [float(x1), float(y1), float(x2), float(y2)]
                    })
    
    # 保存测试结果
    results_df = pd.DataFrame(test_results)
    results_df.to_csv('yolo_test_results.csv', index=False)
    
    print("测试完成！结果已保存到yolo_test_results.csv")

# 辅助函数
def collate_fn(batch):
    """自定义整理函数，处理不同大小的目标标注"""
    imgs, targets, paths = zip(*batch)
    return torch.stack(imgs), targets, paths

def process_predictions(predictions, anchors, num_classes, conf_threshold=0.25, nms_threshold=0.45):
    """处理原始预测输出，应用置信度阈值和NMS"""
    # 这里简化了预测处理逻辑
    # 实际YOLO预测处理更复杂，包括网格坐标转换、锚框调整和NMS
    
    # 简单返回一个假的检测结果
    batch_size = predictions.shape[0]
    detections = []
    
    for i in range(batch_size):
        # 每张图像的检测结果
        img_detections = []
        
        # 简化版的检测处理
        # 实际实现会处理三个不同尺度的特征图
        
        detections.append(img_detections)
    
    return detections

if __name__ == "__main__":
    main()