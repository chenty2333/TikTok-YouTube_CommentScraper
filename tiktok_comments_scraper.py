import logging
from TikTokApi import TikTokApi
import asyncio
import json
import os
import random
from datetime import datetime
import time
import sys

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 设置 ms_token (保留但设为可选)
from config import TIKTOK_MS_TOKEN



# 常用的用户代理列表
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPad; CPU OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1",
]

# 添加调试函数，用于检查对象属性
def debug_object(obj, name="对象"):
    """打印对象的所有属性和方法，帮助调试"""
    logger.debug(f"--- {name} 调试信息 ---")
    if hasattr(obj, '__dict__'):
        for attr_name, attr_value in obj.__dict__.items():
            logger.debug(f"{attr_name}: {attr_value}")
    else:
        logger.debug(f"{name} 没有 __dict__ 属性")
    
    try:
        # 尝试将对象转为字典
        if hasattr(obj, 'as_dict'):
            logger.debug(f"{name} as_dict(): {obj.as_dict()}")
    except:
        pass

# 获取点赞数的函数，尝试多种可能的属性名
def get_like_count(comment):
    """尝试多种可能的方式获取评论点赞数"""
    # 可能的属性名称列表
    like_attrs = ['diggCount', 'likeCount', 'likes', 'like_count', 'likes_count']
    
    # 尝试直接访问属性
    for attr in like_attrs:
        if hasattr(comment, attr):
            return getattr(comment, attr)
    
    # 尝试访问原始数据
    if hasattr(comment, 'as_dict'):
        try:
            comment_dict = comment.as_dict()
            for attr in like_attrs:
                if attr in comment_dict:
                    return comment_dict[attr]
        except:
            pass
    
    # 如果有原始数据属性，检查里面的点赞数
    if hasattr(comment, 'raw_data'):
        raw_data = comment.raw_data
        if isinstance(raw_data, dict):
            for attr in like_attrs:
                if attr in raw_data:
                    return raw_data[attr]
    
    # 尝试处理特殊情况
    if hasattr(comment, 'statistics'):
        stats = comment.statistics
        if isinstance(stats, dict) and 'digg_count' in stats:
            return stats['digg_count']
    
    # 默认值
    return 0

# 创建目录的函数
def ensure_dir_exists(dir_path):
    """确保目录存在，如果不存在则创建"""
    if not os.path.exists(dir_path):
        try:
            os.makedirs(dir_path)
            logger.info(f"创建目录: {dir_path}")
        except Exception as e:
            logger.error(f"创建目录失败: {str(e)}")
            raise

async def get_comments(video_url, count=50, output_filename=None, include_replies=True, 
                      include_user_info=False, include_create_time=False, debug_mode=False,
                      headless=False, browser_type="chromium", use_ms_token=False):
    """
    抓取指定 TikTok 视频的评论
    
    Args:
        video_url: TikTok 视频 URL
        count: 要抓取的评论数量
        output_filename: 输出文件名，如果为 None 则自动生成
        include_replies: 是否包含二级评论(回复)
        include_user_info: 是否包含用户信息
        include_create_time: 是否包含评论创建时间
        debug_mode: 是否开启调试模式
        headless: 是否使用无头模式 (False则显示浏览器)
        browser_type: 浏览器类型 ("webkit" 或 "chromium")
        use_ms_token: 是否使用 ms_token
    """
    # 声明评论列表作用域在整个函数内
    comment_list = []
    
    # 保存已爬取评论的辅助函数
    def save_comments_to_file(comments, file_path, is_final=False):
        try:
            # 确保文件所在目录存在
            file_dir = os.path.dirname(file_path)
            if file_dir:
                ensure_dir_exists(file_dir)
                
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(comments, f, ensure_ascii=False, indent=2)
            if not is_final:  # 不是最终保存时只在调试模式下显示
                if debug_mode:
                    logger.debug(f"已将 {len(comments)} 条评论增量保存到 {file_path}")
            else:
                logger.info(f"✅ 成功保存 {len(comments)} 条评论到 {file_path}")
        except Exception as e:
            logger.error(f"保存评论到文件失败: {str(e)}")
    
    try:
        # 确保输出目录存在
        data_dir = os.path.join("data", "tiktok")
        ensure_dir_exists(data_dir)
        
        # 如果未指定输出文件名，根据时间生成一个
        if output_filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_filename = os.path.join(data_dir, f"tiktok_{timestamp}.json")
        else:
            # 如果指定了输出文件名，确保它在 data/tiktok 目录下
            if not output_filename.startswith(data_dir):
                output_filename = os.path.join(data_dir, os.path.basename(output_filename))
        
        logger.info(f"开始抓取视频评论: {video_url}")
        logger.info(f"计划抓取约 {count} 条评论" + (" (包含回复)" if include_replies else ""))
        logger.info(f"使用配置: 浏览器={browser_type}, 无头模式={headless}, 使用ms_token={use_ms_token}")
        logger.info(f"评论将增量保存到: {output_filename}")

        # 创建一个空的JSON文件，确保文件存在且可写
        save_comments_to_file([], output_filename)

        # 检查 TikTokApi 版本和可用的参数
        try:
            import pkg_resources
            tiktok_api_version = pkg_resources.get_distribution("TikTokApi").version
            logger.info(f"TikTokApi 版本: {tiktok_api_version}")
        except:
            logger.warning("无法获取 TikTokApi 版本信息")
        
        async with TikTokApi() as api:
            # 创建会话
            logger.info("创建 TikTokApi 会话...")
            
            # 根据 TikTokApi 可用参数设置会话
            # 简化会话参数以兼容性更好
            session_params = {}
            
            # 基本参数设置
            if use_ms_token:
                session_params["ms_tokens"] = [ms_token]
                session_params["num_sessions"] = 1
            
            # 尝试设置浏览器相关参数
            session_params["browser"] = browser_type
            session_params["headless"] = headless
            
            # 设置合理的等待时间
            session_params["sleep_after"] = 3
            
            # 显示使用的会话参数
            if debug_mode:
                logger.debug(f"会话参数: {session_params}")
            
            try:
                # 用 try-except 包围以处理不支持的参数
                await api.create_sessions(**session_params)
            except TypeError as e:
                # 如果发生TypeError，可能是不支持的参数
                logger.warning(f"创建会话时出现参数错误: {e}")
                logger.info("尝试使用基本参数创建会话...")
                
                # 回退到最基本的参数
                basic_params = {}
                if use_ms_token:
                    basic_params["ms_tokens"] = [ms_token]
                
                # 只保留最基本的参数
                await api.create_sessions(**basic_params)
            
            # 添加随机延迟，模拟真实用户行为
            delay = random.uniform(1.0, 3.0)
            logger.debug(f"随机延迟 {delay:.2f} 秒...")
            time.sleep(delay)
            
            # 获取视频对象
            video = api.video(url=video_url)
            
            # 抓取评论
            logger.info("开始抓取评论...")
            comment_count = 0
            total_comments = 0  # 包括回复在内的总评论数
            last_save_count = 0  # 上次保存时的评论数
            
            # 使用简单的评论获取参数
            comments_kwargs = {"count": count}
            
            async for comment in video.comments(**comments_kwargs):
                # 处理主评论
                try:
                    # 随机延迟，防止请求过于频繁
                    if random.random() < 0.3:  # 30%的概率添加延迟
                        micro_delay = random.uniform(0.1, 0.8)
                        time.sleep(micro_delay)
                    
                    # 如果是调试模式，输出第一条评论的详细信息以帮助分析
                    if debug_mode and comment_count == 0:
                        debug_object(comment, "第一条评论")
                        
                        # 输出原始数据作为JSON字符串
                        if hasattr(comment, 'as_dict'):
                            try:
                                comment_dict = comment.as_dict()
                                logger.debug(f"评论的as_dict()输出: {json.dumps(comment_dict, indent=2)}")
                            except Exception as e:
                                logger.debug(f"无法将评论转为字典: {str(e)}")
                    
                    # 获取评论点赞数
                    like_count = get_like_count(comment)
                    
                    # 重点关注评论内容和点赞数
                    comment_data = {
                        "text": comment.text if hasattr(comment, 'text') else "",
                        "like_count": like_count,
                        "platform": "tiktok"
                    }
                    
                    # 可选添加用户信息
                    if include_user_info and hasattr(comment, 'author') and hasattr(comment.author, 'uniqueId'):
                        comment_data["user"] = comment.author.uniqueId
                    
                    # 可选添加创建时间
                    if include_create_time and hasattr(comment, 'createTime'):
                        comment_data["create_time"] = comment.createTime
                    
                    # 如果需要获取回复
                    if include_replies and hasattr(comment, 'reply_count') and comment.reply_count > 0:
                        try:
                            # 回复之前增加随机延迟
                            time.sleep(random.uniform(0.5, 1.5))
                            
                            # 尝试获取评论回复
                            reply_count = 0
                            
                            # 使用评论ID获取回复
                            async for reply in comment.replies():
                                # 调试第一条回复
                                if debug_mode and reply_count == 0 and comment_count == 0:
                                    debug_object(reply, "第一条回复")
                                
                                # 获取回复点赞数
                                reply_like_count = get_like_count(reply)
                                
                                reply_data = {
                                    "text": reply.text if hasattr(reply, 'text') else "",
                                    "like_count": reply_like_count,
                                    "platform": "tiktok"
                                }
                                
                                # 可选添加用户信息
                                if include_user_info and hasattr(reply, 'author') and hasattr(reply.author, 'uniqueId'):
                                    reply_data["user"] = reply.author.uniqueId
                                
                                # 可选添加创建时间
                                if include_create_time and hasattr(reply, 'createTime'):
                                    reply_data["create_time"] = reply.createTime
                                    
                                comment_list.append(reply_data)
                                reply_count += 1
                                total_comments += 1
                            
                            if reply_count > 0:
                                logger.info(f"评论 #{comment_count + 1} 获取到 {reply_count} 条回复")
                        except Exception as e:
                            logger.warning(f"获取评论回复时出错: {str(e)}")
                    
                    comment_list.append(comment_data)
                    comment_count += 1
                    total_comments += 1
                    
                    # 每抓取10条评论保存一次
                    if comment_count % 10 == 0:
                        logger.info(f"已抓取 {comment_count} 条主评论 (总计 {total_comments} 条包含回复)...")
                        # 保存当前评论到文件
                        save_comments_to_file(comment_list, output_filename)
                        last_save_count = comment_count
                        
                        # 增加随机休眠
                        rest_time = random.uniform(1.0, 3.0)
                        logger.debug(f"休息 {rest_time:.2f} 秒...")
                        time.sleep(rest_time)
                        
                except Exception as e:
                    logger.warning(f"处理评论时出错: {str(e)}")
                    continue
            
            # 保存最终评论到文件（如果有新增评论）
            if comment_count > last_save_count:
                save_comments_to_file(comment_list, output_filename, is_final=True)
            
            logger.info(f"✅ 评论抓取完成 - {comment_count} 条主评论 (总计 {total_comments} 条包含回复)")
            return comment_list
            
    except KeyboardInterrupt:
        # 用户中断时保存已爬取的评论
        logger.info("用户中断了操作，正在保存已爬取的评论...")
        if comment_list:  # 确保有数据要保存
            save_comments_to_file(comment_list, output_filename, is_final=True)
        logger.info(f"已保存 {len(comment_list)} 条评论到 {output_filename}")
        return comment_list
    except Exception as e:
        # 发生异常时尝试保存已爬取的评论
        logger.error(f"抓取评论失败: {str(e)}")
        if comment_list:  # 确保有数据要保存
            logger.info("尝试保存已爬取的评论...")
            save_comments_to_file(comment_list, output_filename, is_final=True)
            logger.info(f"已保存 {len(comment_list)} 条评论到 {output_filename}")
        raise

def main():
    """主函数，处理命令行参数和调用抓取函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="TikTok 视频评论抓取工具")
    parser.add_argument("--url", type=str, help="TikTok 视频 URL", 
                        default="https://www.tiktok.com/@ccarolinapg/video/7485833744784297238")
    parser.add_argument("--count", type=int, help="要抓取的评论数量", default=100)
    parser.add_argument("--output", type=str, help="输出文件名", default=None)
    parser.add_argument("--no-replies", action="store_true", help="不包含二级评论(回复)")
    parser.add_argument("--include-user", action="store_true", help="包含用户信息")
    parser.add_argument("--include-time", action="store_true", help="包含评论时间")
    parser.add_argument("--debug", action="store_true", help="启用调试模式，输出更多信息")
    parser.add_argument("--show-browser", action="store_true", help="显示浏览器窗口 (不使用无头模式)")
    parser.add_argument("--browser", choices=["webkit", "chromium"], default="chromium", 
                       help="使用的浏览器引擎 (注意: webkit可能不被所有TikTokApi版本支持)")
    parser.add_argument("--no-ms-token", action="store_true", help="不使用 ms_token")
    
    args = parser.parse_args()
    
    # 如果启用了调试模式，将日志级别设置为DEBUG
    if args.debug:
        logger.setLevel(logging.DEBUG)
        logger.debug("调试模式已启用")
    
    # 确保数据目录存在
    data_dir = os.path.join("data", "tiktok")
    if not os.path.exists(data_dir):
        try:
            os.makedirs(data_dir)
            logger.info(f"创建数据目录: {data_dir}")
        except Exception as e:
            logger.error(f"创建数据目录失败: {str(e)}")
    
    try:
        asyncio.run(get_comments(
            args.url, 
            args.count, 
            args.output,
            not args.no_replies,  # 反转 no-replies 参数
            args.include_user,
            args.include_time,
            args.debug,
            not args.show_browser,  # 反转 show-browser 参数
            args.browser,
            not args.no_ms_token  # 反转 no-ms-token 参数
        ))
    except KeyboardInterrupt:
        logger.info("程序已退出")
    except Exception as e:
        logger.error(f"发生错误: {str(e)}")

if __name__ == "__main__":
    main()