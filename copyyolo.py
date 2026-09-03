# convert_to_yolo.py
import os
import pandas as pd
import cv2
from tqdm import tqdm
from sklearn.model_selection import train_test_split

def convert_odir_to_yolo(csv_path, output_dir):
    """将ODIR-5K数据集转换为YOLO格式
    
    Args:
        csv_path: 原始CSV文件路径
        output_dir: 输出目录
    """
    # 读取CSV
    df = pd.read_csv(csv_path)
    
    # 创建输出目录
    os.makedirs(f"{output_dir}/images/train", exist_ok=True)
    os.makedirs(f"{output_dir}/images/val", exist_ok=True)
    os.makedirs(f"{output_dir}/images/test", exist_ok=True)
    os.makedirs(f"{output_dir}/labels/train", exist_ok=True)
    os.makedirs(f"{output_dir}/labels/val", exist_ok=True)
    os.makedirs(f"{output_dir}/labels/test", exist_ok=True)
    
    # 创建类别映射文件
    class_names = ['N', 'D', 'G', 'C', 'A', 'H', 'M', 'O']
    with open(f"{output_dir}/classes.txt", "w") as f:
        for cls in class_names:
            f.write(f"{cls}\n")
    
    # 图像路径和标签提取
    img_paths = df['filepath'].values
    labels = df['target'].apply(lambda x: list(map(int, x.strip('[]').split(',')))).values
    
    # 划分数据集
    train_paths, test_paths, train_labels, test_labels = train_test_split(
        img_paths, labels, test_size=0.2, random_state=42
    )
    train_paths, val_paths, train_labels, val_labels = train_test_split(
        train_paths, train_labels, test_size=0.2, random_state=42
    )
    
    # 处理函数
    def process_set(img_paths, labels, set_name):
        for i, (img_path, label) in enumerate(tqdm(zip(img_paths, labels), desc=f"处理{set_name}集")):
            # 使用指定的基础目录
            base_dir = "您的基础目录路径"  # 例如："./data" 或 "../../dataset"
            rel_img_path = os.path.normpath(os.path.join(base_dir, img_path))[3:]
            img = cv2.imread(rel_img_path)
            if img is None:
                print(f"无法读取图像: {img_path}")
                print(f"尝试的相对路径: {rel_img_path}")
                continue
                
            h, w, _ = img.shape
            
            # 拷贝图像到输出目录
            img_filename = os.path.basename(img_path)
            dst_img_path = f"{output_dir}/images/{set_name}/{img_filename}"
            cv2.imwrite(dst_img_path, img)
            
            # 创建YOLO格式标签文件
            # 在YOLO格式中，每行为: class_id center_x center_y width height
            # 所有值都相对于图像宽高进行归一化
            label_filename = os.path.splitext(img_filename)[0] + ".txt"
            with open(f"{output_dir}/labels/{set_name}/{label_filename}", "w") as f:
                # 遍历标签，对每个为1的类别生成边界框
                for cls_id, cls_val in enumerate(label):
                    if cls_val == 1:
                        # 假设眼部区域占据图像中心的70%区域
                        center_x, center_y = 0.5, 0.5  # 中心点
                        width, height = 0.7, 0.7       # 宽高
                        f.write(f"{cls_id} {center_x} {center_y} {width} {height}\n")
    
    # 处理训练集、验证集和测试集
    process_set(train_paths, train_labels, "train")
    process_set(val_paths, val_labels, "val")
    process_set(test_paths, test_labels, "test")
    
    # 创建数据配置文件
    with open(f"{output_dir}/odir.yaml", "w") as f:
        f.write(f"path: {output_dir}\n")
        f.write(f"train: images/train\n")
        f.write(f"val: images/val\n")
        f.write(f"test: images/test\n\n")
        f.write(f"nc: {len(class_names)}\n")
        f.write(f"names: {class_names}\n")

if __name__ == "__main__":
    convert_odir_to_yolo(
        './archive/data_copy_utf-8.csv', 
        './odir_yolo'
    )
    print("转换完成！")