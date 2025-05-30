#!/usr/bin/env python3
import requests
import argparse
import time
import os
import json
from typing import Optional


class MinerUClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')
    
    def convert_pdf(self, pdf_path: str) -> dict:
        """上传PDF文件并开始转换任务"""
        with open(pdf_path, 'rb') as f:
            response = requests.post(
                f'{self.base_url}/convert/',
                files={'file': f}
            )
        
        if response.status_code != 200:
            raise Exception(f"上传失败: {response.text}")
            
        return response.json()
    
    def get_task_status(self, task_id: str) -> dict:
        """获取任务状态"""
        response = requests.get(f'{self.base_url}/status/{task_id}')
        
        if response.status_code != 200:
            raise Exception(f"获取状态失败: {response.text}")
            
        return response.json()
    
    def get_file_list(self, task_id: str) -> list:
        """获取文件列表"""
        response = requests.get(f'{self.base_url}/files/{task_id}')
        
        if response.status_code != 200:
            raise Exception(f"获取文件列表失败: {response.text}")
            
        return response.json()['files']
    
    def download_file(self, task_id: str, file_name: str, output_dir: Optional[str] = None) -> str:
        """下载文件"""
        response = requests.get(f'{self.base_url}/download/{task_id}/{file_name}', stream=True)
        
        if response.status_code != 200:
            raise Exception(f"下载文件失败: {response.text}")
        
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
            output_path = os.path.join(output_dir, file_name)
        else:
            output_path = file_name
            
        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
                
        return output_path
    
    def download_zip(self, task_id: str, output_path: Optional[str] = None) -> str:
        """下载所有文件的ZIP压缩包"""
        response = requests.get(f'{self.base_url}/download-zip/{task_id}', stream=True)
        
        if response.status_code != 200:
            raise Exception(f"下载ZIP文件失败: {response.text}")
        
        # 获取文件名
        content_disposition = response.headers.get('content-disposition', '')
        filename = None
        if 'filename=' in content_disposition:
            filename = content_disposition.split('filename=')[1].strip('"\'')
        
        if not filename:
            filename = f"mineru_results_{task_id}.zip"
        
        if output_path:
            if os.path.isdir(output_path):
                output_path = os.path.join(output_path, filename)
        else:
            output_path = filename
            
        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
                
        return output_path
    
    def wait_for_completion(self, task_id: str, check_interval: int = 5, timeout: int = 300) -> dict:
        """等待任务完成"""
        start_time = time.time()
        
        while True:
            status = self.get_task_status(task_id)
            
            if status['status'] == 'completed':
                return status
            
            if status['status'] == 'failed':
                raise Exception(f"任务失败: {status.get('error', '未知错误')}")
                
            if time.time() - start_time > timeout:
                raise Exception(f"任务超时，当前状态: {status['status']}")
                
            print(f"任务状态: {status['status']}，等待 {check_interval} 秒...")
            time.sleep(check_interval)


def main():
    parser = argparse.ArgumentParser(description="MinerU PDF转换客户端")
    parser.add_argument("pdf_file", help="要转换的PDF文件路径")
    parser.add_argument("--server", default="http://localhost:8000", help="MinerU API服务器地址")
    parser.add_argument("--output", "-o", help="输出目录")
    parser.add_argument("--wait", "-w", action="store_true", help="等待任务完成")
    parser.add_argument("--interval", "-i", type=int, default=5, help="状态检查间隔（秒）")
    parser.add_argument("--timeout", "-t", type=int, default=300, help="超时时间（秒）")
    parser.add_argument("--zip", "-z", action="store_true", help="下载ZIP压缩包而不是单独文件")
    
    args = parser.parse_args()
    
    client = MinerUClient(args.server)
    
    try:
        # 上传PDF
        print(f"上传文件: {args.pdf_file}")
        result = client.convert_pdf(args.pdf_file)
        task_id = result['task_id']
        print(f"任务ID: {task_id}")
        
        if not args.wait:
            print("文件已上传，任务正在处理中。")
            print(f"您可以使用以下命令检查状态:")
            print(f"  curl {args.server}/status/{task_id}")
            return
        
        # 等待任务完成
        print("等待任务完成...")
        status = client.wait_for_completion(task_id, args.interval, args.timeout)
        print(f"任务完成！状态: {status['status']}")
        
        output_dir = args.output or f"mineru_output_{task_id}"
        
        # 如果选择下载ZIP压缩包
        if args.zip:
            print(f"下载ZIP压缩包...")
            zip_path = client.download_zip(task_id, output_dir)
            print(f"已下载ZIP文件: {zip_path}")
            return
        
        # 否则下载单独的文件
        # 获取文件列表
        files = client.get_file_list(task_id)
        print(f"可用文件: {', '.join(files)}")
        
        # 下载所有文件
        print(f"下载文件到: {output_dir}")
        
        for file_name in files:
            output_path = client.download_file(task_id, file_name, output_dir)
            print(f"已下载: {output_path}")
            
        print("全部文件下载完成！")
        
    except Exception as e:
        print(f"错误: {str(e)}")
        return 1


if __name__ == "__main__":
    exit(main()) 