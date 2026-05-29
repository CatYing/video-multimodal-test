from openai import OpenAI
import httpx
import base64
import os

# 创建定制的会话
transport = httpx.HTTPTransport(proxy=None, verify=False)
http_client = httpx.Client(transport=transport)

client = OpenAI(
    base_url="http://xx.xx.xx.xx:8899/v1",
    api_key="xx",  # 必填，同X-HW-ID
    http_client=http_client
)

base_path = r"D:\Document\融合视频\图片检查\DTS2025070519586"


#  base 64 编码格式
def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")


before = encode_image(os.path.join(base_path, "before.webp"))
after = encode_image(os.path.join(base_path, "after.jfif"))
with open(os.path.join(base_path, "process.txt"), "r", encoding="utf-8") as f:
    manipulation = f.read()

try:
    prompt = '''
    你是一个专业的 EPG (电子节目指南) 自动化测试工程师，擅长通过视觉与逻辑的双重校验来发现 IPTV 系统的深层缺陷。

    请分析以下两张图片：
    - 【第一张图 (pre)】：执行操作前的当前状态。
    - 【第二张图 (post)】：在 pre 状态下，用户按遥控器执行了 “{manipulation}” 后的实际结果。

    ## 第一阶段：预期逻辑推理（思维链）
    在查看 post 图片前，请基于专业知识判断：执行 “{manipulation}” 后的**标准预期结果**是什么？
    - 如果是“主页”，应该跳转到图标整齐、无遮挡的桌面。
    - 如果是“确定/播放”，应该进入视频播放器或详情页。
    - 如果是“方向键”，焦点应该发生移动，且旧焦点应消失。

    ## 第二阶段：缺陷判定标准（严格执行）

    **若 post 界面符合以下任一情况，必须判定为 FAIL：**

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

    ## 关联性判定逻辑
    - **PASS**: `post` 界面是 `pre` 经过 `{manipulation}` 后的**干净、正确、唯一**的后续状态。
    - **FAIL**: 操作后画面没变、画面叠影、视频窗口黑屏、或跳转到了错误的页面。

    ## 输出要求
    请按以下 JSON 格式输出，逻辑判断必须严谨：

    ```json
    {{
      "pre_has_defect": true或false,
      "post_has_defect": true或false,
      "logical_consistency": "一致/不一致（请分析操作 {manipulation} 是否产生了正确的反馈）",
      "pre_defect_type": "normal或缺陷类型",
      "post_defect_type": "缺陷类型（如：UI重叠、逻辑不符、局部黑屏等）",
      "pre_defect_description": "描述",
      "post_defect_description": "描述（重点描述操作后的异常：如'跳转主页后残留了前一页的菜单文字'）",
      "pre_defect_severity": "none/normal/moderate/severe/critical",
      "post_defect_severity": "none/normal/moderate/severe/critical",
      "overall_verdict": "PASS或FAIL",
      "confidence": 0.0到1.0
    }}
    '''.format(manipulation=manipulation)

    completion = client.chat.completions.create(
        model="model",
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/webp;base64,{before}"}
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jfif;base64,{after}"}
                    },
                    {"type": "text", "text": prompt}
                ]
            }
        ],
        stream=True,
        extra_body={"chat_template_kwargs": {"enable_thinking": False}}
    )
    res = ""
    for chunk in completion:
        if chunk.choices:
            res += chunk.choices[0].delta.content
            print(chunk.choices[0].delta.content, end="")
except Exception as err:
    print(f"错误发生: {err}")