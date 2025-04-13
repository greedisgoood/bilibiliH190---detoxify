#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Bilibili Cookie 快速设置工具

这个脚本允许用户通过命令行参数直接设置 Bilibili Cookie。
适用于已经知道自己的 Cookie 值，想要快速配置的用户。

使用方法：
python set_cookie.py --sessdata "xxx" --bili_jct "xxx" --userid "xxx"

或者直接粘贴完整的 cookie 字符串：
python set_cookie.py --cookie "完整的cookie字符串"
"""

import os
import json
import argparse
import re

def parse_cookie_string(cookie_str):
    """解析cookie字符串为字典"""
    cookies = {}
    for item in cookie_str.split("; "):
        if "=" in item:
            key, value = item.split("=", 1)
            cookies[key] = value
    return cookies

def extract_key_cookies(cookie_dict):
    """从完整cookie字典中提取关键cookie"""
    key_cookies = {}
    for key in ["SESSDATA", "bili_jct", "DedeUserID", "DedeUserID__ckMd5", "sid"]:
        if key in cookie_dict:
            key_cookies[key] = cookie_dict[key]
    return key_cookies

def save_cookies_to_file(cookies, filename="cookies.json"):
    """将Cookie保存到文件"""
    try:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(cookies, f, indent=4)
        print(f"Cookie已保存到 {filename}")
        return True
    except Exception as e:
        print(f"保存Cookie时出错: {e}")
        return False

def save_cookies_to_env(cookies, filename=".env"):
    """将Cookie保存到.env文件"""
    try:
        # 构建Cookie字符串
        cookie_str = "; ".join([f"{key}={value}" for key, value in cookies.items()])
        
        # 检查.env文件是否存在
        if os.path.exists(filename):
            # 读取现有内容
            with open(filename, "r", encoding="utf-8") as f:
                lines = f.readlines()
            
            # 查找并替换BILIBILI_COOKIE行
            cookie_line_found = False
            for i, line in enumerate(lines):
                if line.startswith("BILIBILI_COOKIE="):
                    lines[i] = f"BILIBILI_COOKIE={cookie_str}\n"
                    cookie_line_found = True
                    break
            
            # 如果没有找到BILIBILI_COOKIE行，则添加
            if not cookie_line_found:
                lines.append(f"BILIBILI_COOKIE={cookie_str}\n")
            
            # 写回文件
            with open(filename, "w", encoding="utf-8") as f:
                f.writelines(lines)
        else:
            # 创建新文件
            with open(filename, "w", encoding="utf-8") as f:
                f.write(f"BILIBILI_COOKIE={cookie_str}\n")
        
        print(f"Cookie已保存到 {filename}")
        return True
    except Exception as e:
        print(f"保存Cookie到.env文件时出错: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="设置Bilibili Cookie")
    
    # 两种模式：直接设置完整cookie或分别设置各个字段
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--cookie", help="完整的cookie字符串")
    group.add_argument("--sessdata", help="SESSDATA值")
    
    # 如果使用分别设置模式，这些参数是必需的
    parser.add_argument("--bili_jct", help="bili_jct值")
    parser.add_argument("--userid", help="DedeUserID值")
    
    # 可选参数
    parser.add_argument("--ckmd5", help="DedeUserID__ckMd5值")
    parser.add_argument("--sid", help="sid值")
    
    # 保存选项
    parser.add_argument("--json", action="store_true", help="保存到cookies.json")
    parser.add_argument("--env", action="store_true", help="保存到.env文件")
    parser.add_argument("--both", action="store_true", help="同时保存到两种格式")
    
    args = parser.parse_args()
    
    # 默认同时保存到两种格式
    if not (args.json or args.env or args.both):
        args.both = True
    
    cookies = {}
    
    if args.cookie:
        # 从完整cookie字符串中提取
        all_cookies = parse_cookie_string(args.cookie)
        cookies = extract_key_cookies(all_cookies)
        
        # 检查是否提取到必要的cookie
        required_cookies = ["SESSDATA", "bili_jct", "DedeUserID"]
        missing_cookies = [name for name in required_cookies if name not in cookies]
        
        if missing_cookies:
            print(f"警告：从提供的cookie字符串中缺少必要的Cookie: {', '.join(missing_cookies)}")
            
            # 尝试从字符串中直接提取
            for required in missing_cookies:
                match = re.search(f"{required}=([^;]+)", args.cookie)
                if match:
                    cookies[required] = match.group(1)
            
            # 再次检查
            missing_cookies = [name for name in required_cookies if name not in cookies]
            if missing_cookies:
                print(f"错误：无法提取所有必要的Cookie，缺少: {', '.join(missing_cookies)}")
                return
    else:
        # 检查必要参数
        if not args.sessdata or not args.bili_jct or not args.userid:
            print("错误：使用分别设置模式时，--sessdata、--bili_jct和--userid参数是必需的")
            return
        
        # 从参数中构建cookie字典
        cookies["SESSDATA"] = args.sessdata
        cookies["bili_jct"] = args.bili_jct
        cookies["DedeUserID"] = args.userid
        
        if args.ckmd5:
            cookies["DedeUserID__ckMd5"] = args.ckmd5
        
        if args.sid:
            cookies["sid"] = args.sid
    
    # 保存cookie
    if args.json or args.both:
        save_cookies_to_file(cookies)
    
    if args.env or args.both:
        save_cookies_to_env(cookies)
    
    print("\nCookie设置完成！现在你可以运行bilibili_auto.py来使用这些Cookie了。")

if __name__ == "__main__":
    main() 