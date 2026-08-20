from playwright.sync_api import sync_playwright


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()

        page.goto("https://weibo.com/", wait_until="domcontentloaded")
        print("微博页面已经打开，进入交互调试状态...")

        # 挂起脚本并保持事件响应，你可以自由操作网页
        page.pause()

        browser.close()


if __name__ == "__main__":
    main()