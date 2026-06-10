"""
交互式微博Cookie获取工具
"""
import json
import requests
import sys
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

def get_cookie_from_browser():
    """通过交互式方式获取Cookie"""
    print("\n" + "="*70)
    print("微博 Cookie 获取工具")
    print("="*70)
    
    print("""
📝 请按照以下步骤操作：

1️⃣  打开浏览器（Chrome 或 Edge）
2️⃣  访问: https://weibo.com
3️⃣  登录你的微博账号
4️⃣  按 F12 打开开发者工具
5️⃣  点击顶部的 "Application" 标签
6️⃣  左侧展开 "Cookies" -> 选择 "weibo.com"
7️⃣  在右侧的 Cookie 列表中找到 "SUB" 这一行
8️⃣  复制其 "Value" 列的内容（很长的字符串）

完成上述步骤后，按 Enter 继续...
""")
    
    input("⏳ 按 Enter 继续...")
    
    print("\n现在请粘贴你复制的 SUB Cookie 值：")
    print("(" + "X" * 50 + " <- 大概这个长度)")
    
    sub_value = input("\n请粘贴 SUB 值: ").strip()
    
    if len(sub_value) < 30:
        print("❌ 输入的值太短，请确保完整复制")
        return None
    
    # 保存到cookies文件
    cookies = {
        'SUB': sub_value,
        'timestamp': __import__('datetime').datetime.now().isoformat()
    }
    
    cookies_file = Path(__file__).parent / 'weibo_cookies.json'
    with open(cookies_file, 'w', encoding='utf-8') as f:
        json.dump(cookies, f, indent=2, ensure_ascii=False)
    
    print(f"\n✓ Cookie 已保存到: {cookies_file}")
    print(f"✓ SUB 值: {sub_value[:30]}...{sub_value[-10:]}")
    
    return sub_value

def verify_cookie(sub_value):
    """验证Cookie是否有效"""
    print("\n⏳ 正在验证 Cookie 有效性...")
    
    try:
        url = 'https://weibo.com/ajax/statuses/buildComments'
        params = {
            'is_reload': 1,
            'id': '5192118454714744',
            'is_show_bulletin': 2,
            'count': 1,
            'uid': '',
            'fetch_level': 0,
            'locale': 'zh-CN'
        }
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Referer': 'https://weibo.com',
            'X-Requested-With': 'XMLHttpRequest',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        }
        cookies = {'SUB': sub_value}

        response = requests.get(url, params=params, headers=headers, cookies=cookies, timeout=15)
        response.raise_for_status()
        data = response.json()

        if data.get('ok') == 1:
            print("✓ Cookie 验证成功！")
            return True

        if data.get('ok') == -100:
            print("❌ Cookie 无效：微博返回登录跳转")
            print(f"   登录地址: {data.get('url', 'https://weibo.com/login.php')}")
            return False

        print(f"❌ Cookie 无效（API返回异常）: {data}")
        return False
    except Exception as e:
        print(f"验证过程出错: {e}")
        return False

def main():
    # 检查是否已有有效的cookies文件
    cookies_file = Path(__file__).parent / 'weibo_cookies.json'
    
    if cookies_file.exists():
        with open(cookies_file, 'r') as f:
            cookies = json.load(f)
            print(f"\n✓ 检测到现有 Cookie 文件")
            print(f"  时间: {cookies.get('timestamp', '未知')}")
            
            choice = input("\n是否要更新 Cookie？(y/n): ").strip().lower()
            if choice != 'y':
                print("✓ 使用现有 Cookie，准备采集")
                return
    
    # 获取新的Cookie
    sub_value = get_cookie_from_browser()
    
    if sub_value:
        # 验证Cookie
        if verify_cookie(sub_value):
            print("\n✓ 现在可以运行爬虫了！")
            print("  运行命令: D:/cv/python.exe weibo_crawler.py")
        else:
            print("\n❌ Cookie 验证失败，请重新获取")
    else:
        print("\n❌ 未获取到有效的 Cookie")

if __name__ == '__main__':
    main()
