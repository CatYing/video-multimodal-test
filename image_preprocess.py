import os
import json
import shutil


def process_images_by_screenshot(jsonl_path, image_root_dir, output_dir):
    """
    根据 JSONL 文件中的 step、action 和 screenshot 相对路径，分类并复制图片。

    :param jsonl_path: jsonl 文件的路径
    :param image_root_dir: 图片的根目录（用于和 jsonl 中的相对路径拼接）
    :param output_dir: 生成新文件夹的目标根目录
    """
    # 确保输出总目录存在
    os.makedirs(output_dir, exist_ok=True)

    # 1. 构建字典，key 是 step，value 是对应的条目字典
    step_dict = {}

    with open(jsonl_path, 'r', encoding='utf-8') as f:
        for line in f:
            if not line.strip():
                continue
            item = json.loads(line.strip())

            # 读取 step 字段，并统一转换为整型
            step = item.get('step')
            if step is not None:
                step_dict[int(step)] = item

    print(f"成功解析 JSONL，共获取到 {len(step_dict)} 个独立的 step。")

    # 2 & 3. 遍历字典，寻找 step-1 的项并处理图片
    for current_step, current_item in step_dict.items():
        previous_step = current_step - 1

        # 检查是否存在 step-1 的数据
        if previous_step in step_dict:
            previous_item = step_dict[previous_step]

            # 获取当前 step 的 action 字段
            action = current_item.get('action', 'UNKNOWN_ACTION')

            # 拼接基础文件夹名称，例如: "1-2-DPAD_DOWN"
            folder_name_base = f"{previous_step}-{current_step}-{action}"

            # 防重名处理（如添加 _0, _1 序号）
            folder_name = folder_name_base
            counter = 0
            target_folder_path = os.path.join(output_dir, folder_name)
            while os.path.exists(target_folder_path):
                folder_name = f"{folder_name_base}_{counter}"
                target_folder_path = os.path.join(output_dir, folder_name)
                counter += 1

            # 从 json 字典中获取相对路径
            rel_curr_path = current_item.get('screenshot')
            rel_prev_path = previous_item.get('screenshot')

            if rel_curr_path and rel_prev_path:
                # 【核心修改】：将图片的根目录与相对路径拼接，得到图片在电脑上的真实绝对（或完整）路径
                src_curr_path = os.path.join(image_root_dir, rel_curr_path)
                src_prev_path = os.path.join(image_root_dir, rel_prev_path)

                if not os.path.exists(src_curr_path) or not os.path.exists(src_prev_path):
                    continue

                # 新建文件夹
                os.makedirs(target_folder_path, exist_ok=True)

                # 提取图片本来的文件名，用来作为保存到目标文件夹里的名字
                curr_img_name = os.path.basename(rel_curr_path)
                prev_img_name = os.path.basename(rel_prev_path)

                # 复制图片到新文件夹中
                try:
                    # 处理前一个 step 的图片
                    if os.path.exists(src_prev_path):
                        shutil.copy(src_prev_path, os.path.join(target_folder_path, "prev.png"))
                    else:
                        print(f"警告: 找不到 step-1 的图片，拼接后的路径为: {src_prev_path}")

                    # 处理当前 step 的图片
                    if os.path.exists(src_curr_path):
                        shutil.copy(src_curr_path, os.path.join(target_folder_path, "curr.png"))
                    else:
                        print(f"警告: 找不到当前 step 的图片，拼接后的路径为: {src_curr_path}")

                    print(f"✅ 已成功创建文件夹【{folder_name}】并复制相关图片。")
                except Exception as e:
                    print(f"❌ 复制图片时出错: {e}")
            else:
                print(f"提示: step {previous_step} 或 step {current_step} 的字典中缺少 screenshot 字段。")


# ================= 使用示例 =================
if __name__ == "__main__":
    # JSONL_FILE = "D:\Document\融合视频\图片检查\new_dataset\events.jsonl"  # 你的 jsonl 文件路径
    JSONL_FILE = "run_20260520_145129/events.jsonl"  # 你的 jsonl 文件路径
    # IMAGE_ROOT_DIR = r"D:\Document\融合视频\图片检查\new_dataset\run_20260520_145129"  # 👈 这里填写你图片存放的根目录
    IMAGE_ROOT_DIR = "run_20260520_145129/"  # 👈 这里填写你图片存放的根目录
    # OUTPUT_DIRECTORY = r"D:\Document\融合视频\图片检查\new_dataset\dataset"  # 整理后的输出根文件夹
    OUTPUT_DIRECTORY = "./dataset"  # 整理后的输出根文件夹

    # 传入三个参数
    process_images_by_screenshot(JSONL_FILE, IMAGE_ROOT_DIR, OUTPUT_DIRECTORY)