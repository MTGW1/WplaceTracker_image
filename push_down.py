import os
import shutil
import subprocess
import datetime
import time
import ssl
import aiohttp
import re
import requests
import urllib3
import sys
from urllib.parse import unquote
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

git_url = "https://github.com/MTGW1/WplaceTracker_image.git"
into_repo_path = "/images"

download_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "download") # 下载路径(非克隆)

def PushDownImage(file_info_list: list):
    # 检查下载的文件夹是否存在
    if not os.path.exists(download_path):
        os.makedirs(download_path)
    
    # 设置重试策略
    session = requests.Session()
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "OPTIONS"]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    for i, file_info in enumerate(file_info_list):
        file_name = file_info['name']
        file_url = file_info['url']
        
        print(f"正在下载 ({i+1}/{len(file_info_list)}): {file_name}")
        
        # 尝试下载函数
        def download_file(url):
            response = session.get(url, stream=True, verify=False, timeout=30)
            total_size = int(response.headers.get('content-length', 0))
            
            if response.status_code == 200:
                with open(os.path.join(download_path, file_name), 'wb') as f:
                    if total_size == 0:
                        f.write(response.content)
                    else:
                        downloaded = 0
                        for data in response.iter_content(chunk_size=8192):
                            downloaded += len(data)
                            f.write(data)
                            done = int(50 * downloaded / total_size)
                            sys.stdout.write(f"\r[{'=' * done}{' ' * (50 - done)}] {int(downloaded/total_size*100)}%")
                            sys.stdout.flush()
                print() # 换行
                return True
            else:
                print(f"HTTP状态码: {response.status_code}")
                return False

        try:
            if not download_file(file_url):
                # 如果失败，尝试使用 GitHub 原始链接作为备用
                print("尝试使用备用链接下载...")
                fallback_url = f"https://github.com/MTGW1/WplaceTracker_image/raw/main/images/{file_name}"
                if not download_file(fallback_url):
                     # 如果还失败，尝试使用加速镜像 (可选，视情况而定，这里仅作为最后的尝试)
                    print("尝试使用镜像链接下载...")
                    mirror_url = f"https://raw.gitmirror.com/MTGW1/WplaceTracker_image/main/images/{file_name}"
                    if not download_file(mirror_url):
                        print(f"无法下载文件 {file_name}")

        except Exception as e:
            print(f"\n下载文件 {file_name} 时出错: {e}")

def get_filename_with_timerange(start_time: datetime.datetime, end_time: datetime.datetime) -> list:
    start_str = start_time.strftime("%Y%m%d_%H%M%S")
    end_str = end_time.strftime("%Y%m%d_%H%M%S")
    
    # 使用 GitHub API 获取文件列表
    api_url = "https://api.github.com/repos/MTGW1/WplaceTracker_image/contents/images"
    print(f"正在访问 GitHub API: {api_url}")
    
    try:
        response = requests.get(api_url, verify=False)
        if response.status_code != 200:
            print(f"无法访问 GitHub API，状态码: {response.status_code}")
            print(f"响应内容: {response.text}")
            return []
        
        files_data = response.json()
        print(f"从 API 获取到 {len(files_data)} 个文件信息。")
        
        matched_files = []
        for file_item in files_data:
            file_name = file_item['name']
            download_url = file_item['download_url']
            
            # 抓取png文件名中的时间戳，支持下划线和连字符
            timestamp_match = re.search(r'(\d{8}[-_]\d{6})', file_name)
            if timestamp_match:
                file_time_str = timestamp_match.group(1)
                try:
                    if '-' in file_time_str:
                        file_time = datetime.datetime.strptime(file_time_str, "%Y%m%d-%H%M%S")
                    else:
                        file_time = datetime.datetime.strptime(file_time_str, "%Y%m%d_%H%M%S")
                    
                    if start_time <= file_time <= end_time:
                        matched_files.append({'name': file_name, 'url': download_url})
                except ValueError:
                    print(f"无法解析时间戳: {file_time_str}")
        
        return matched_files
        
    except Exception as e:
        print(f"访问 API 时出错: {e}")
        return []

def main():
    # 输入日期
    # 格式: YYYY-MM-DD HH:MM:SS
    start_date_input = input("请输入年月日 (格式: YYYYMMDD): ")
    # 搞兼容
    if len(start_date_input) == 8:
        start_date_input = f"{start_date_input[:4]}-{start_date_input[4:6]}-{start_date_input[6:]}"
    elif len(start_date_input) == 6: # YYMMDD
        start_date_input = f"20{start_date_input[:2]}-{start_date_input[2:4]}-{start_date_input[4:]}"
    elif len(start_date_input) == 4: # MMDD
        current_year = datetime.datetime.now().year
        start_date_input = f"{current_year}-{start_date_input[:2]}-{start_date_input[2:]}"
    elif len(start_date_input) == 2: # DD
        current_year = datetime.datetime.now().year
        current_month = datetime.datetime.now().month
        start_date_input = f"{current_year}-{current_month:02d}-{start_date_input}"
    elif len(start_date_input) == 0: # 默认为今天
        current_year = datetime.datetime.now().year
        current_month = datetime.datetime.now().month
        current_day = datetime.datetime.now().day
        start_date_input = f"{current_year}-{current_month:02d}-{current_day:02d}"
    elif int(start_date_input) < 0: # 负数表示几天前
        days_ago = abs(int(start_date_input))
        target_date = datetime.datetime.now() - datetime.timedelta(days=days_ago)
        start_date_input = target_date.strftime("%Y-%m-%d")
    start_time_imput = input("请输入开始时间 (格式: HHMMSS): ")
    if len(start_time_imput) == 6:
        start_time_imput = f"{start_time_imput[:2]}:{start_time_imput[2:4]}:{start_time_imput[4:]}"
    elif len(start_time_imput) == 4:
        start_time_imput = f"{start_time_imput[:2]}:{start_time_imput[2:]}:00"
    elif len(start_time_imput) == 2:
        start_time_imput = f"{start_time_imput}:00:00"
    elif len(start_time_imput) == 0:
        start_time_imput = "00:00:00"
    elif int(start_time_imput) < 0: # 负数表示几小时前
        hours_ago = abs(int(start_time_imput))
        target_time = datetime.datetime.now() - datetime.timedelta(hours=hours_ago)
        start_time_imput = target_time.strftime("%H:%M:%S")
    end_date_input = input("请输入结束年月日 (格式: YYYYMMDD): ")
    if len(end_date_input) == 8:
        end_date_input = f"{end_date_input[:4]}-{end_date_input[4:6]}-{end_date_input[6:]}"
    elif len(end_date_input) == 6: # YYMMDD
        end_date_input = f"20{end_date_input[:2]}-{end_date_input[2:4]}-{end_date_input[4:]}"
    elif len(end_date_input) == 4: # MMDD
        current_year = datetime.datetime.now().year
        end_date_input = f"{current_year}-{end_date_input[:2]}-{end_date_input[2:]}"
    elif len(end_date_input) == 2: # DD
        current_year = datetime.datetime.now().year
        current_month = datetime.datetime.now().month
        end_date_input = f"{current_year}-{current_month:02d}-{end_date_input}"
    elif len(end_date_input) == 0: # 默认为今天
        current_year = datetime.datetime.now().year
        current_month = datetime.datetime.now().month
        current_day = datetime.datetime.now().day
        end_date_input = f"{current_year}-{current_month:02d}-{current_day:02d}"
    elif int(end_date_input) < 0: # 负数表示几天前
        days_ago = abs(int(end_date_input))
        target_date = datetime.datetime.now() - datetime.timedelta(days=days_ago)
        end_date_input = target_date.strftime("%Y-%m-%d")
    end_time_input = input("请输入结束时间 (格式: HHMMSS): ")
    if len(end_time_input) == 6:
        end_time_input = f"{end_time_input[:2]}:{end_time_input[2:4]}:{end_time_input[4:]}"
    elif len(end_time_input) == 4:
        end_time_input = f"{end_time_input[:2]}:{end_time_input[2:]}:00"
    elif len(end_time_input) == 2:
        end_time_input = f"{end_time_input}:00:00"
    elif len(end_time_input) == 0:
        # if今天
        if start_date_input == datetime.datetime.now().strftime("%Y-%m-%d"):
            end_time_input = datetime.datetime.now().strftime("%H:%M:%S")
        else:
            end_time_input = "23:59:59"
    elif int(end_time_input) < 0: # 负数表示几小时前
        hours_ago = abs(int(end_time_input))
        target_time = datetime.datetime.now() - datetime.timedelta(hours=hours_ago)
        end_time_input = target_time.strftime("%H:%M:%S")

    start_datetime_str = f"{start_date_input}_{start_time_imput}"
    end_datetime_str = f"{end_date_input}_{end_time_input}"
    start_datetime = datetime.datetime.strptime(start_datetime_str, "%Y-%m-%d_%H:%M:%S")
    end_datetime = datetime.datetime.strptime(end_datetime_str, "%Y-%m-%d_%H:%M:%S")
    print(f"开始时间: {start_datetime}, 结束时间: {end_datetime}")
    matched_files = get_filename_with_timerange(start_datetime, end_datetime)
    if not matched_files:
        print("在指定时间范围内没有找到匹配的文件。")
        return
    print(f"找到 {len(matched_files)} 个匹配的文件，开始下载...")
    try:
        PushDownImage(matched_files)
    except Exception as e:
        print(f"下载过程中出现错误: {e}")
        return
    print("所有文件下载完成。")

if __name__ == "__main__":
    main()