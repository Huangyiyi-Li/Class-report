import io
import os
import shutil
import subprocess
import sys
import zipfile
from datetime import datetime
from pathlib import Path

import streamlit as st


ROOT_DIR = Path(__file__).resolve().parent.parent
RUNS_DIR = ROOT_DIR / "runs"
PYTHON = sys.executable
SUBJECTS = ["语文", "数学", "英语", "物理", "化学", "生物", "政治", "历史", "地理"]
LESSON_TYPES = ["新课", "复习课", "讲题课"]


def make_run_dir(label: str) -> Path:
    safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in label).strip("._")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = RUNS_DIR / f"{timestamp}_{safe or 'validation'}"
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def save_inputs(base_dir: Path, excel_file, lesson_file):
    for version_name in ("v1.0", "v1.1.a", "v1.1.b"):
        version_dir = base_dir / version_name
        version_dir.mkdir(parents=True, exist_ok=True)

        excel_path = version_dir / excel_file.name
        excel_path.write_bytes(excel_file.getbuffer())

        lesson_path = version_dir / lesson_file.name
        lesson_path.write_bytes(lesson_file.getbuffer())


def run_command(command, env, cwd):
    completed = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return {
        "command": command,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def collect_outputs(folder: Path):
    exts = {".html", ".pdf", ".json"}
    outputs = []
    for file in sorted(folder.iterdir()):
        if file.is_file() and file.suffix.lower() in exts:
            outputs.append(file)
    return outputs


def zip_run_dir(run_dir: Path) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for file in run_dir.rglob("*"):
            if file.is_file():
                zf.write(file, file.relative_to(run_dir))
    buffer.seek(0)
    return buffer.getvalue()


st.set_page_config(page_title="ICAS 三版本验证器", layout="wide")
st.title("ICAS 三版本验证器")
st.caption("上传一个 Excel 和一个教案文件，顺序输出 v1.0 / v1.1.a / v1.1.b 三版报告。")

with st.sidebar:
    st.subheader("运行参数")
    run_label = st.text_input("本次验证名称", value="classroom_validation")
    api_key = st.text_input("ARK API Key", type="password")
    model_name = st.text_input("模型名称", value=os.getenv("ARK_MODEL_NAME", "ep-20251223144447-7946z"))
    base_url = st.text_input("Base URL", value=os.getenv("ARK_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3"))
    subject = st.selectbox("v1.1.b 学科", SUBJECTS, index=0)
    lesson_type = st.selectbox("v1.1.b 课型", LESSON_TYPES, index=0)
    generate_pdf = st.checkbox("v1.0 / v1.1.a 同时生成 PDF", value=True)

col_left, col_right = st.columns(2)
with col_left:
    excel_file = st.file_uploader("上传课堂 Excel", type=["xlsx", "xls"])
with col_right:
    lesson_file = st.file_uploader("上传教案文件", type=["docx", "doc", "txt"])

run_button = st.button("生成三版报告", type="primary", use_container_width=True)

if run_button:
    if not api_key.strip():
        st.error("请先填写 API Key。")
        st.stop()
    if excel_file is None or lesson_file is None:
        st.error("请同时上传 Excel 和教案文件。")
        st.stop()

    run_dir = make_run_dir(run_label)
    save_inputs(run_dir, excel_file, lesson_file)

    env = os.environ.copy()
    env["ARK_API_KEY"] = api_key.strip()
    env["ARK_MODEL_NAME"] = model_name.strip()
    env["ARK_BASE_URL"] = base_url.strip()

    st.info(f"输出目录：{run_dir}")

    tasks = [
        {
            "name": "v1.0",
            "command": [
                PYTHON,
                str(ROOT_DIR / "versions" / "v1_0" / "auto_analyze_simple.py"),
                str(run_dir / "v1.0"),
                "--no-open",
                *( [] if generate_pdf else ["--no-pdf"] ),
            ],
        },
        {
            "name": "v1.1.a",
            "command": [
                PYTHON,
                str(ROOT_DIR / "src" / "auto_analyze_simple.py"),
                str(run_dir / "v1.1.a"),
                "--no-open",
                *( [] if generate_pdf else ["--no-pdf"] ),
            ],
        },
        {
            "name": "v1.1.b",
            "command": [
                PYTHON,
                str(ROOT_DIR / "v3.0" / "auto_analyze_v3.py"),
                str(run_dir / "v1.1.b"),
                "--subject",
                subject,
                "--lesson-type",
                lesson_type,
                "--output",
                str(run_dir / "v1.1.b"),
            ],
        },
    ]

    results = []
    progress = st.progress(0)
    status_box = st.empty()

    for index, task in enumerate(tasks, start=1):
        status_box.write(f"正在运行 {task['name']}...")
        results.append((task["name"], run_command(task["command"], env=env, cwd=ROOT_DIR)))
        progress.progress(index / len(tasks))

    status_box.write("运行结束。")

    success_count = sum(1 for _, result in results if result["returncode"] == 0)
    if success_count == len(results):
        st.success("三个版本都已执行完成。")
    else:
        st.warning(f"{success_count}/{len(results)} 个版本执行成功，请检查日志。")

    for version_name, result in results:
        version_dir = run_dir / version_name
        outputs = collect_outputs(version_dir)
        with st.expander(f"{version_name} 结果", expanded=True):
            st.code(" ".join(result["command"]))
            st.write(f"退出码：{result['returncode']}")
            if outputs:
                st.write("输出文件：")
                for file in outputs:
                    st.write(str(file))
            if result["stdout"]:
                st.text_area(f"{version_name} stdout", result["stdout"], height=220)
            if result["stderr"]:
                st.text_area(f"{version_name} stderr", result["stderr"], height=140)

    zip_bytes = zip_run_dir(run_dir)
    st.download_button(
        label="下载本次验证结果 ZIP",
        data=zip_bytes,
        file_name=f"{run_dir.name}.zip",
        mime="application/zip",
        use_container_width=True,
    )
