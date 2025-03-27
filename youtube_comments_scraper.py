import os
import json
import argparse
import logging
import time
import random
import re
import socket
from datetime import datetime
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import requests
import ssl

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 设置API密钥
from config import YOUTUBE_API_KEY


# 最大重试次数
MAX_RETRIES = 3

# 保存目录
SAVE_DIR = os.path.join("data", "youtube")

def get_video_id_from_url(url):
    """从YouTube URL中提取视频ID"""
    # 检查是否直接是视频ID (通常是11个字符的字母数字组合)
    if re.match(r'^[A-Za-z0-9_-]{11}$', url):
        return url
    
    # 处理各种YouTube URL格式
    if "youtu.be/" in url:
        return url.split("youtu.be/")[-1].split("?")[0].split("&")[0]
    
    elif "youtube.com/shorts/" in url:
        return url.split("youtube.com/shorts/")[-1].split("?")[0].split("&")[0]
    
    elif "youtube.com/watch" in url:
        match = re.search(r'v=([A-Za-z0-9_-]{11})', url)
        if match:
            return match.group(1)
    
    # 无法识别的URL格式
    logger.error(f"无法从URL中提取视频ID: {url}")
    return None

def validate_video_id(video_id):
    """验证视频ID是否有效"""
    if not video_id:
        return False
    
    # 检查格式是否符合YouTube视频ID (通常11个字符)
    if not re.match(r'^[A-Za-z0-9_-]{11}$', video_id):
        return False
    
    # 尝试访问YouTube API验证视频是否存在
    try:
        response = requests.get(f"https://www.youtube.com/oembed?url=http://www.youtube.com/watch?v={video_id}&format=json")
        return response.status_code == 200
    except:
        # 请求失败但不一定意味着视频不存在，可能是网络问题
        return True

def save_comments_to_file(comments, file_path, is_final=False):
    """保存评论到文件"""
    try:
        # 确保目录存在
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(comments, f, ensure_ascii=False, indent=2)
        if is_final:
            logger.info(f"✅ 成功保存 {len(comments)} 条评论到 {file_path}")
        else:
            logger.debug(f"已将 {len(comments)} 条评论增量保存到 {file_path}")
    except Exception as e:
        logger.error(f"保存评论到文件失败: {str(e)}")

def execute_with_retry(func, *args, **kwargs):
    """执行函数并在失败时重试"""
    retries = 0
    while retries < MAX_RETRIES:
        try:
            return func(*args, **kwargs)
        except (ssl.SSLError, socket.error, ConnectionError) as e:
            retries += 1
            wait_time = 2 ** retries  # 指数退避策略
            logger.warning(f"网络错误: {str(e)}, 第{retries}次重试, 等待{wait_time}秒...")
            time.sleep(wait_time)
        except Exception as e:
            # 其他非网络错误，直接抛出
            raise e
    
    # 所有重试都失败
    raise Exception(f"在{MAX_RETRIES}次尝试后仍然失败")

def get_comments(video_url, count=100, output_filename=None, include_replies=True,
                sort_by="relevance", debug_mode=False):
    """
    获取YouTube视频的评论
    
    Args:
        video_url: YouTube视频URL或ID
        count: 要获取的评论数量
        output_filename: 输出文件名
        include_replies: 是否包含回复评论
        sort_by: 排序方式 ('relevance' 或 'time')
        debug_mode: 是否开启调试模式
    """
    if debug_mode:
        logger.setLevel(logging.DEBUG)
        
    # 评论列表
    comment_list = []
    
    try:
        # 如果未指定输出文件名，根据时间和视频ID生成一个
        video_id = get_video_id_from_url(video_url)
        
        if not video_id:
            logger.error("无法获取有效的视频ID，请检查URL格式")
            return comment_list
        
        if output_filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_filename = os.path.join(SAVE_DIR, f"youtube_{video_id}_{timestamp}.json")
        else:
            # 确保输出路径在指定目录内
            if not output_filename.startswith(SAVE_DIR):
                output_filename = os.path.join(SAVE_DIR, os.path.basename(output_filename))
        
        # 创建一个空的JSON文件，确保文件存在且可写
        save_comments_to_file([], output_filename)
            
        # 验证视频ID
        if not validate_video_id(video_id):
            logger.error(f"视频ID无效或视频不存在: {video_id}")
            return comment_list
            
        logger.info(f"开始获取YouTube视频评论: {video_id}")
        logger.info(f"计划获取约 {count} 条评论" + (" (包含回复)" if include_replies else ""))
        
        # 创建YouTube API客户端，设置超时
        youtube = build('youtube', 'v3', developerKey=API_KEY, cache_discovery=False)
        
        # 评论请求参数
        comment_kwargs = {
            'part': 'snippet',
            'videoId': video_id,
            'maxResults': min(100, count),  # YouTube API一次最多返回100条
            'order': sort_by,  # 'relevance' 或 'time'
            'textFormat': 'plainText'
        }
        
        # 获取评论线程
        next_page_token = None
        comment_count = 0
        total_comments = 0
        last_save_count = 0
        
        while comment_count < count:
            # 添加分页token（如果有）
            if next_page_token:
                comment_kwargs['pageToken'] = next_page_token
                
            # 获取评论线程
            try:
                # 使用重试机制执行API请求
                response = execute_with_retry(
                    lambda: youtube.commentThreads().list(**comment_kwargs).execute()
                )
                
                # 检查是否有评论
                if 'items' not in response or len(response['items']) == 0:
                    logger.info("该视频没有评论或评论已被禁用")
                    break
                    
            except HttpError as e:
                if "videoNotFound" in str(e) or "404" in str(e):
                    logger.error(f"视频不存在或无法访问: {video_id}")
                elif "commentsDisabled" in str(e):
                    logger.error("该视频已禁用评论功能")
                else:
                    logger.error(f"YouTube API错误: {e}")
                break
                
            # 处理评论
            for item in response['items']:
                # 避免超过要求的评论数
                if comment_count >= count:
                    break
                    
                # 随机延迟，防止请求过于频繁
                if random.random() < 0.2:  # 20%的概率添加延迟
                    micro_delay = random.uniform(0.1, 0.5)
                    time.sleep(micro_delay)
                
                try:
                    # 获取评论信息
                    comment_info = item['snippet']['topLevelComment']['snippet']
                    
                    # 创建精简的评论数据
                    comment_data = {
                        "text": comment_info['textDisplay'],
                        "like_count": comment_info['likeCount'],
                        "platform": "youtube"
                    }
                    
                    # 获取回复评论
                    if include_replies and item['snippet']['totalReplyCount'] > 0:
                        try:
                            # 使用重试机制获取回复
                            replies_response = execute_with_retry(
                                lambda: youtube.comments().list(
                                    part='snippet',
                                    parentId=item['id'],
                                    maxResults=100  # 最多获取100条回复
                                ).execute()
                            )
                            
                            for reply_item in replies_response.get('items', []):
                                reply_info = reply_item['snippet']
                                
                                # 创建精简的回复数据
                                reply_data = {
                                    "text": reply_info['textDisplay'],
                                    "like_count": reply_info['likeCount'],
                                    "platform": "youtube"
                                }
                                
                                comment_list.append(reply_data)
                                total_comments += 1
                                
                            if len(replies_response.get('items', [])) > 0:
                                logger.info(f"评论 #{comment_count + 1} 获取到 {len(replies_response.get('items', []))} 条回复")
                        
                        except Exception as e:
                            logger.warning(f"获取评论回复时出错: {str(e)}")
                    
                    comment_list.append(comment_data)
                    comment_count += 1
                    total_comments += 1
                    
                    # 每获取10条评论保存一次
                    if comment_count % 10 == 0:
                        logger.info(f"已获取 {comment_count} 条主评论 (总计 {total_comments} 条包含回复)...")
                        # 保存当前评论到文件
                        save_comments_to_file(comment_list, output_filename)
                        last_save_count = comment_count
                        
                        # 增加随机休眠
                        rest_time = random.uniform(1.0, 2.0)
                        logger.debug(f"休息 {rest_time:.2f} 秒...")
                        time.sleep(rest_time)
                        
                except Exception as e:
                    logger.warning(f"处理评论时出错: {str(e)}")
                    continue
            
            # 检查是否有下一页
            next_page_token = response.get('nextPageToken')
            if not next_page_token:
                break
        
        # 保存最终评论到文件（如果有新增评论）
        if comment_count > last_save_count:
            save_comments_to_file(comment_list, output_filename, is_final=True)
        
        logger.info(f"✅ 评论获取完成 - {comment_count} 条主评论 (总计 {total_comments} 条包含回复)")
        return comment_list
        
    except KeyboardInterrupt:
        # 用户中断时保存已获取的评论
        logger.info("用户中断了操作，正在保存已获取的评论...")
        if comment_list:
            save_comments_to_file(comment_list, output_filename, is_final=True)
        logger.info(f"已保存 {len(comment_list)} 条评论到 {output_filename}")
        return comment_list
        
    except Exception as e:
        # 发生异常时尝试保存已获取的评论
        logger.error(f"获取评论失败: {str(e)}")
        if comment_list:
            logger.info("尝试保存已获取的评论...")
            save_comments_to_file(comment_list, output_filename, is_final=True)
        return comment_list

def main():
    """处理命令行参数并运行程序"""
    parser = argparse.ArgumentParser(description="YouTube 视频评论获取工具")
    parser.add_argument("--url", type=str, required=True, help="YouTube 视频 URL 或 ID")
    parser.add_argument("--count", type=int, help="要获取的评论数量", default=100)
    parser.add_argument("--output", type=str, help="输出文件名", default=None)
    parser.add_argument("--no-replies", action="store_true", help="不包含回复评论")
    parser.add_argument("--sort", choices=["relevance", "time"], default="relevance", 
                        help="评论排序方式 (relevance: 相关性, time: 时间)")
    parser.add_argument("--debug", action="store_true", help="启用调试模式")
    
    args = parser.parse_args()
    
    if not API_KEY or API_KEY == "YOUR_API_KEY_HERE":
        logger.error("请设置您的YouTube API密钥")
        logger.info("您可以通过环境变量设置: export YOUTUBE_API_KEY='您的API密钥'")
        logger.info("或者在脚本中直接修改API_KEY变量")
        return
    
    try:
        get_comments(
            args.url,
            args.count,
            args.output,
            not args.no_replies,
            args.sort,
            args.debug
        )
    except KeyboardInterrupt:
        logger.info("程序已退出")
    except Exception as e:
        logger.error(f"发生错误: {str(e)}")

if __name__ == "__main__":
    main()
