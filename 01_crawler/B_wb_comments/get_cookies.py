"""
从浏览器获取微博 Cookie 的辅助脚本
使用 Selenium + Chrome 自动化
"""
import json
import time

try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
except ImportError:
    print("❌ 需要安装 selenium")
    print("   运行: D:/cv/python.exe -m pip install selenium")
    exit(1)

def get_weibo_cookies():
    """自动打开浏览器并获取微博cookies"""
    
    # 创建Chrome浏览器实例
    options = webdriver.ChromeOptions()
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    
    print("⏳ 正在启动浏览器...")
    driver = webdriver.Chrome(options=options)
    
    try:
        # 打开微博首页
        print("⏳ 正在访问微博首页...")
        driver.get('https://weibo.com')
        
        # 等待用户登录（最多等待2分钟）
        print("\n📱 请在打开的浏览器中登录微博账号")
        print("   登录完成后，程序会自动获取 Cookie")
        print("   如果浏览器未打开，请手动打开 Chrome 并访问 https://weibo.com")
        
        # 等待用户登录完成
        WebDriverWait(driver, 120).until(
            lambda driver: len(driver.get_cookies()) > 5
        )
        
        # 获取所有cookies
        all_cookies = driver.get_cookies()
        cookies_dict = {cookie['name']: cookie['value'] for cookie in all_cookies}
        
        print("\n✓ 成功获取 Cookie！")
        print("\n以下是你的微博 Cookie（需要保存在脚本中）：\n")
        print("COOKIES = {")
        for name in ['SUB', 'SUBP', '_U', 'SINAGLOBAL']:
            if name in cookies_dict:
                print(f"    '{name}': '{cookies_dict[name]}',")
        print("}")
        
        # 保存到文件
        with open('weibo_cookies.json', 'w', encoding='utf-8') as f:
            json.dump(cookies_dict, f, indent=2, ensure_ascii=False)
        print(f"\n✓ Cookie 已保存到 weibo_cookies.json")
        
        return cookies_dict
        
    except Exception as e:
        print(f"❌ 出错: {e}")
        return None
    finally:
        driver.quit()

if __name__ == '__main__':
    cookies = get_weibo_cookies()
