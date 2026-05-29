import base64
import os
import re
import json
from concurrent.futures import ThreadPoolExecutor, as_completed

import httpx
import pandas as pd
from openai import OpenAI

# ==================== 配置区域 ====================
# 你的样本根目录路径
DATA_DIR = "./dataset"
# 最终结果保存路径（支持 .csv 或 .xlsx）
OUTPUT_FILE = "qwen_model_evaluation_results.xlsx"
# 并发数
MAX_WORKERS = 20


# 创建定制的会话
transport = httpx.HTTPTransport(proxy=None, verify=False)
http_client = httpx.Client(transport=transport)


extra_body = {
    "chat_template_kwargs": {"enable_thinking": True}
}

client = OpenAI(
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    api_key="sk-8610acc657d84dda9c0208a2ac074f14",
    http_client=http_client
)


# =================================================

def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")


def call_model(prev_path, curr_path, action):
    before = encode_image(prev_path)
    after = encode_image(curr_path)

    try:
        prompt = '''
        你是一个专业的 EPG (电子节目指南) 自动化测试工程师，擅长通过视觉与逻辑的双重校验来发现 IPTV 系统的深层缺陷。

        ## 任务
        请分析以下两张图片：
        - 【第一张图 (pre)】：执行操作前的当前状态。
        - 【第二张图 (post)】：在 pre 状态下，用户按遥控器执行了 “{manipulation}” 后的实际结果。
        你需要判断pre图片在进行遥控器操作后，post图片的状态是否符合预期。

        遥控器操作都包含：
        - DPAD_UP：向上按钮
        - DPAD_DOWN：向下按钮
        - DPAD_LEFT：向左按钮
        - DPAD_RIGHT：向右按钮
        - DPAD_CENTER：确认按钮
        - BACK：返回按钮

        ## 第一阶段：预期逻辑推理（思维链）
        在查看 post 图片前，请基于专业知识判断：执行 “{manipulation}” 后的**标准预期结果**是什么？
        - 如果是“返回”，应该跳转逻辑上的上一层页面，此时有可能只有焦点位置变化。
        - 如果是“确定”，应该进入视频播放器或详情页。
        - 如果是“方向键”，且该方向有移动空间的情况下，焦点应该发生移动，且旧焦点应消失。

        ## 第二阶段：缺陷判定标准

        界面中可能存在一下缺陷：

        1. **逻辑不一致 (Logical Inconsistency) [关键增项]**:
           - **操作无效**：执行操作后，界面内容与 `pre` 完全一致，且无任何加载提示。
           - **跳转错误**：执行的操作（如“进入直播”）与 `post` 呈现的内容（如“留在设置页面”）完全不符。

        2. **状态残留与渲染污染 (UI Ghosting/Pollution) [关键增项]**:
           - **元素重叠**：`post` 界面出现了本该消失的 `pre` 界面元素（例如：跳转主页后，原来的弹窗文字或二级菜单依然叠在主页图标上）。
           - **脏界面**：文字、图片、按钮位移后，原位置留有残影，或多个 UI 组件在同一位置堆叠导致无法辨认。

        3. **核心功能区异常 (Functional Area Failure)**:
           - **局部黑屏**：UI 框架加载成功，但核心内容区（如视频播放窗口、海报位）呈现纯黑色或死点。
           - **焦点丢失/多重焦点**：操作后找不到高亮选框，或者屏幕上同时出现了两个高亮选框。

        4. **视觉崩溃 (Visual Crash)**:
           - 全屏黑屏、花屏、严重的乱码（符号化）、或文字重叠导致的视觉混乱。

        ## 第三阶段：客观指标检查
        - **文件大小**: 若 post 比 pre 文件减小 >30%，警惕局部或全局黑屏。
        - **分辨率**: 若 post 分辨率异常，说明画面可能发生了非预期的拉伸或裁剪。

        ## 第四阶段：关联性逻辑判定
        - **PASS**: `post` 界面是 `pre` 经过 `{manipulation}` 后的**干净、正确、唯一**的后续状态。
        - **FAIL**: 操作后前后逻辑不符合预期，或出现了第二阶段中列举的缺陷。

        ## 判断原则【**必须遵守**】
        - 核心判断的点在于，在进行指定操作后，从前一张图到后一张图的变化是否合理，只要逻辑合理就可判断为PASS。

        ## 特殊场景
        - 若点击方向键后，画面没有发生变化，需要判断该方向是否还有操作空间，如果没有操作空间的情况下点击该方向键后画面无变化（如光标已经在最左侧菜单栏，此时再进行DPAD_LEFT操作后画面不变），或从存在循环现象（如进行DPAD_DOWN后光标从最下跳到最上）属于正常现象。
        - 

        ## 输出要求
        请按以下 JSON 格式输出，逻辑判断必须严谨：

        ```json
        {{
          "logical_consistency": "一致/不一致（请分析操作 {manipulation} 是否产生了正确的反馈）",
          "description": "判断依据，即判断是PASS或FAIL的具体原因",
          "overall_verdict": "PASS或FAIL",
          "confidence": 0.0到1.0
        }}
        '''.format(manipulation=action)

        completion = client.chat.completions.create(
            model="qwen3.5-397b-a17b",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{before}"}
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{after}"}
                        },
                        {"type": "text", "text": prompt}
                    ]
                }
            ],
            stream=False,
            extra_body=extra_body,
        )
        res = completion.choices[0].message.content
        return res
    except Exception as err:
        print(f"错误发生: {err}")
        return ""


def parse_folder_name(folder_name):
    """
    解析文件夹名称，匹配规则：step-1 - step - action
    例如: "1-2-DPAD_DOWN" -> prev_step="1", curr_step="2", action="DPAD_DOWN"
    """
    # 使用正则表达式安全匹配：数字-数字-任意字符
    pattern = r"^(\d+)-(\d+)-(.*)$"
    match = re.match(pattern, folder_name)
    if match:
        return match.group(1), match.group(2), match.group(3)
    return None, None, None


def mock_model_call(prev_img_path, curr_img_path, action):
    """
    模型调用接口（占位符）
    请在此处填充你实际的 LLaVA/GPT-4V/Qwen-VL 等模型的推理代码
    """
    # ----------------------------------------------------
    response = call_model(prev_img_path, curr_img_path, action)
    # ----------------------------------------------------
    return response


def parse_model_output(raw_output):
    """
    解析模型的 JSON 输出，提取 overall_verdict
    """
    try:
        # 预防模型输出带有 ```json ...``` 标记，先做清洗
        cleaned_output = raw_output.strip()
        if cleaned_output.startswith("```json"):
            cleaned_output = cleaned_output.split("```json")[-1].split("```")[0].strip()
        elif cleaned_output.startswith("```"):
            cleaned_output = cleaned_output.split("```")[1].split("```")[0].strip()

        data = json.loads(cleaned_output)
        # 提取关键字段，若不存在则默认为 "Unknown"
        verdict = data.get("overall_verdict", "Unknown")
        return verdict
    except Exception as e:
        print(f"解析模型 JSON 失败: {e}。原始输出: {raw_output}")
        return "Parse Error"


def process_item(item):
    """
    处理单个文件夹：解析命名、校验图片、调用模型并解析结果。
    返回结果字典；不符合规则或缺少图片时返回 None。
    """
    item_path = os.path.join(DATA_DIR, item)

    # 只处理符合命名规则的文件夹
    if not os.path.isdir(item_path):
        return None

    prev_step, curr_step, action = parse_folder_name(item)

    # 如果解析失败，跳过该文件夹
    if not prev_step:
        print(f"跳过不符合命名规则的文件夹: {item}")
        return None

    prev_img_path = os.path.join(item_path, "prev.png")
    curr_img_path = os.path.join(item_path, "curr.png")

    # 检查图片是否存在
    if not (os.path.exists(prev_img_path) and os.path.exists(curr_img_path)):
        print(f"警告: 文件夹 {item} 中缺少 prev.png 或 curr.png，已跳过。")
        return None

    print(f"正在处理步骤: {prev_step} -> {curr_step} | Action: {action}")

    # 1. 喂给模型并获取原始输出
    raw_model_output = mock_model_call(prev_img_path, curr_img_path, action)

    # 2. 解析模型输出，获取是否通过的判定
    overall_verdict = parse_model_output(raw_model_output)

    print(f"完成步骤: {prev_step} -> {curr_step} | Action: {action}  判断结果：{overall_verdict}")

    # 3. 返回数据
    return {
        "前一步骤(Prev Step)": prev_step,
        "后一步骤(Curr Step)": curr_step,
        "动作(Action)": action,
        "是否通过(Overall Verdict)": overall_verdict,
        "模型原始输出(Raw Output)": raw_model_output
    }


def main():
    if not os.path.exists(DATA_DIR):
        print(f"错误: 找不到指定的根目录 '{DATA_DIR}'")
        return

    items = os.listdir(DATA_DIR)
    results = []

    # 并发调用模型进行推理
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(process_item, item): item for item in items}
        for future in as_completed(futures):
            try:
                result = future.result()
            except Exception as err:
                print(f"处理文件夹 {futures[future]} 时发生异常: {err}")
                continue
            if result is not None:
                results.append(result)

    # 按步骤排序，保证并发后输出顺序稳定
    results.sort(key=lambda r: (int(r["前一步骤(Prev Step)"]), int(r["后一步骤(Curr Step)"])))

    # 4. 转换为 DataFrame 并导出表格
    if results:
        df = pd.DataFrame(results)

        # 根据你的后缀名决定导出格式
        if OUTPUT_FILE.endswith(".xlsx"):
            # 需要安装 openpyxl: pip install openpyxl
            df.to_excel(OUTPUT_FILE, index=False)
        else:
            df.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")

        print(f"\n处理完成！结果已成功保存至: {OUTPUT_FILE}")
    else:
        print("\n没有找到有效的步骤文件夹或未生成任何结果。")


if __name__ == "__main__":
    main()