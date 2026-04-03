#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
音频下载、转换和合并脚本
功能：
1. 从Excel文件读取D列的音频下载链接
2. 下载所有音频文件
3. 使用ffmpeg转换为最高质量MP3格式
4. 按顺序合并所有MP3文件为一个文件
"""

import os
import sys
import pandas as pd
import requests
from pathlib import Path
import subprocess
from tqdm import tqdm
import time

# 设置UTF-8输出编码（解决Windows终端编码问题）
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 配置
EXCEL_FILE = "第七次课0318/语文-7段-0918-0948.xlsx"
DOWNLOAD_DIR = "第七次课0318/downloads"
CONVERTED_DIR = "第七次课0318/converted"
OUTPUT_FILE = "第七次课0318/0918-0948.mp3"
# 使用绝对路径并规范化
FFMPEG_PATH = os.path.abspath("ffmpeg-2025-12-22-git-c50e5c7778-essentials_build/bin/ffmpeg.exe")

# MP3最高质量设置：320kbps CBR，48kHz采样率
MP3_QUALITY_PARAMS = [
    "-codec:a", "libmp3lame",
    "-b:a", "320k",           # 320kbps比特率（MP3最高质量）
    "-ar", "48000",           # 48kHz采样率
    "-ac", "2",               # 立体声
    "-q:a", "0"               # 最高质量参数
]


def print_section(title):
    """打印分节标题"""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def create_directories():
    """创建必要的目录"""
    print_section("初始化")
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    os.makedirs(CONVERTED_DIR, exist_ok=True)
    print(f"✓ 创建目录: {DOWNLOAD_DIR}/")
    print(f"✓ 创建目录: {CONVERTED_DIR}/")


def read_excel_links():
    """从Excel文件读取音频链接"""
    print_section("读取Excel文件")
    print(f"正在读取: {EXCEL_FILE}")
    
    df = pd.read_excel(EXCEL_FILE)
    links = df['file_path'].tolist()
    
    print(f"✓ 成功读取 {len(links)} 个音频链接")
    return df, links


def download_file(url, filename, index, total):
    """下载单个文件并显示进度"""
    try:
        print(f"\n[{index}/{total}] 正在下载: {filename}")
        print(f"  URL: {url}")
        
        response = requests.get(url, stream=True)
        response.raise_for_status()
        
        total_size = int(response.headers.get('content-length', 0))
        
        with open(filename, 'wb') as f:
            if total_size == 0:
                f.write(response.content)
                print(f"  ✓ 下载完成")
            else:
                with tqdm(total=total_size, unit='B', unit_scale=True, 
                         desc=f"  进度", ncols=70) as pbar:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            pbar.update(len(chunk))
                print(f"  ✓ 下载完成 ({total_size / 1024 / 1024:.2f} MB)")
        
        return True
    except Exception as e:
        print(f"  ✗ 下载失败: {str(e)}")
        return False


def download_audio_files(df, links):
    """下载所有音频文件"""
    print_section("下载音频文件")
    
    downloaded_files = []
    total = len(links)
    success_count = 0
    
    for idx, (index, row) in enumerate(df.iterrows(), 1):
        url = row['file_path']
        segment_index = row['segment_index']
        
        # 从URL提取文件扩展名
        ext = os.path.splitext(url)[-1]
        filename = os.path.join(DOWNLOAD_DIR, f"{segment_index:02d}{ext}")
        
        if download_file(url, filename, idx, total):
            downloaded_files.append({
                'segment_index': segment_index,
                'original_file': filename
            })
            success_count += 1
    
    print(f"\n✓ 下载完成: {success_count}/{total} 个文件")
    return downloaded_files


def convert_to_mp3(files):
    """将音频文件转换为最高质量MP3格式"""
    print_section("转换为MP3格式（最高质量）")
    print(f"质量设置: 320kbps CBR, 48kHz, 立体声")
    
    converted_files = []
    total = len(files)
    success_count = 0
    
    for idx, file_info in enumerate(files, 1):
        input_file = os.path.abspath(file_info['original_file'])
        segment_index = file_info['segment_index']
        output_file = os.path.abspath(os.path.join(CONVERTED_DIR, f"{segment_index:02d}.mp3"))

        print(f"\n[{idx}/{total}] 正在转换: {os.path.basename(input_file)} → {os.path.basename(output_file)}")

        # 构建命令字符串（转义路径中的空格和特殊字符）
        cmd = f'"{FFMPEG_PATH}" -i "{input_file}" {" ".join(MP3_QUALITY_PARAMS)} -y "{output_file}"'

        try:
            # 运行ffmpeg，使用errors='ignore'忽略编码错误
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8',
                errors='ignore',
                shell=True  # 使用shell=True执行命令字符串
            )

            if result.returncode == 0:
                file_size = os.path.getsize(output_file) / 1024 / 1024
                print(f"  ✓ 转换成功 ({file_size:.2f} MB)")
                converted_files.append({
                    'segment_index': segment_index,
                    'file': output_file
                })
                success_count += 1
            else:
                print(f"  ✗ 转换失败")
                if result.stderr:
                    print(f"  错误信息: {result.stderr[:200]}")
        except Exception as e:
            print(f"  ✗ 转换失败: {str(e)}")
    
    print(f"\n✓ 转换完成: {success_count}/{total} 个文件")
    return converted_files


def merge_mp3_files(files):
    """合并所有MP3文件为一个文件"""
    print_section("合并MP3文件")
    
    # 按segment_index排序
    files.sort(key=lambda x: x['segment_index'])
    
    # 创建concat文件列表
    concat_file = os.path.abspath("concat_list.txt")
    with open(concat_file, 'w', encoding='utf-8') as f:
        for file_info in files:
            # 使用绝对路径，并转义特殊字符
            f.write(f"file '{os.path.abspath(file_info['file'])}'\n")

    print(f"正在合并 {len(files)} 个MP3文件...")
    print(f"输出文件: {OUTPUT_FILE}")

    # 使用concat协议合并，保持最高质量
    cmd = f'"{FFMPEG_PATH}" -f concat -safe 0 -i "{concat_file}" -c copy -y "{os.path.abspath(OUTPUT_FILE)}"'

    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding='utf-8',
            errors='ignore',
            shell=True  # 使用shell=True执行命令字符串
        )

        if result.returncode == 0:
            file_size = os.path.getsize(OUTPUT_FILE) / 1024 / 1024
            print(f"✓ 合并成功!")
            print(f"  文件大小: {file_size:.2f} MB")
            print(f"  文件位置: {os.path.abspath(OUTPUT_FILE)}")

            # 清理concat文件
            os.remove(concat_file)
            return True
        else:
            print(f"✗ 合并失败")
            if result.stderr:
                print(f"错误信息: {result.stderr[:200]}")
            return False
    except Exception as e:
        print(f"✗ 合并失败: {str(e)}")
        return False


def main():
    """主函数"""
    start_time = time.time()
    
    print("\n" + "=" * 60)
    print("  音频下载、转换和合并工具")
    print("=" * 60)
    
    try:
        # 步骤1: 创建目录
        create_directories()
        
        # 步骤2: 读取Excel
        df, links = read_excel_links()
        
        # 步骤3: 下载音频文件
        downloaded_files = download_audio_files(df, links)
        
        if not downloaded_files:
            print("\n✗ 没有成功下载任何文件，程序终止")
            return 1
        
        # 步骤4: 转换为MP3
        converted_files = convert_to_mp3(downloaded_files)
        
        if not converted_files:
            print("\n✗ 没有成功转换任何文件，程序终止")
            return 1
        
        # 步骤5: 合并MP3文件
        success = merge_mp3_files(converted_files)
        
        # 完成
        elapsed_time = time.time() - start_time
        print_section("处理完成")
        print(f"总耗时: {elapsed_time:.1f} 秒")
        
        if success:
            print("\n✓ 所有任务已成功完成!")
            print(f"✓ 最终输出文件: {os.path.abspath(OUTPUT_FILE)}")
            return 0
        else:
            print("\n✗ 部分任务执行失败")
            return 1
            
    except Exception as e:
        print(f"\n✗ 程序执行出错: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
