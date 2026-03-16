import os
import re
import pandas as pd
import logging
import time
from typing import List, Dict, Optional
from seleniumbase import SB
from bs4 import BeautifulSoup

class WBParserBrowser:
    def __init__(self, result_dir: str):
        self.result_dir = result_dir
        os.makedirs(self.result_dir, exist_ok=True)
        logging.basicConfig(
            filename=os.path.join(self.result_dir, 'errors.log'),
            level=logging.ERROR,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )

    def parse_product(self, sb, url: str) -> Optional[Dict]:
        try:
            # Открываем страницу в режиме undetected-chromedriver
            sb.uc_open_with_reconnect(url, 15)
            # Ждем прогрузки SKU (теперь это основной признак страницы товара)
            sb.wait_for_element('[data-testid]', timeout=15)
            
            # Если выскочила капча, пробуем нажать "Я не робот" (если есть)
            if sb.is_element_visible('iframe[src*="challenge"]'):
                 sb.uc_gui_click_captcha()
            
            # Получаем HTML-код страницы
            html = sb.get_page_source()
            soup = BeautifulSoup(html, 'html.parser')
            
            # Извлекаем данные (селекторы для 2026 года)
            # Заголовок: ищем в span с классом productImtName или старые варианты
            title_elem = soup.select_one('[class*="productImtName"], .product-page__header h1, h1')
            title = title_elem.get_text(strip=True) if title_elem else "Не указано"
            
            # Цена: ищем в разных возможных блоках (WB часто меняет классы)
            price_elem = soup.select_one('[class*="productLinePriceWallet"], ins.price-block__final-price, .price-block__final-price, .current-price')
            price_text = price_elem.get_text(strip=True) if price_elem else "0"
            # Очистка цены от символов рубля и пробелов
            price = int(re.sub(r'\D', '', price_text)) if price_text else 0
            
            # Отзывы
            reviews_elem = soup.select_one('[class*="reviewCount"], .product-review__count, .address-rate-count')
            reviews_text = reviews_elem.get_text(strip=True) if reviews_elem else "0"
            reviews = int(re.sub(r'\D', '', reviews_text)) if reviews_text else 0
            
            # Наличие
            is_available = "Нет в наличии" if soup.select_one('.product-page__order-status--out-of-stock, .sold-out, [class*="sold-out"]') else "Доступно"

            return {
                'title': title,
                'final_price': price,
                'reviews': reviews,
                'delivery_date': is_available,
                'url': url
            }
        except Exception as e:
            logging.error(f"Error parsing {url}: {str(e)}")
            return None

def read_links(filepath: str) -> List[str]:
    links = []
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                link = line.strip()
                if link:
                    links.append(link)
    return links

def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    main_link_file = os.path.join(base_dir, 'main_base', 'main_link.txt')
    compare_link_file = os.path.join(base_dir, 'compare_base', 'compare_link.txt')
    result_dir = os.path.join(base_dir, 'result')
    result_file_txt = os.path.join(result_dir, 'result.txt')
    result_file_xlsx = os.path.join(result_dir, 'result.xlsx')

    main_links = read_links(main_link_file)
    compare_links = read_links(compare_link_file)
    all_links = main_links + compare_links
    
    if not all_links:
        print("No links found.")
        return

    print(f"Starting Browser-based parser for {len(all_links)} links...")
    print("This method is slower but bypasses WBAAS protection.")
    
    results = []
    parser = WBParserBrowser(result_dir)

    # Запускаем SeleniumBase в режиме UC (Undetected Chromedriver)
    with SB(uc=True, headless2=True) as sb:
        for i, url in enumerate(all_links, 1):
            print(f"Processing {i}/{len(all_links)}: {url}")
            data = parser.parse_product(sb, url)
            if data:
                results.append(data)
            else:
                print(f"  [!] Failed to get data for {url}. See errors.log")
            
            # Небольшая пауза между страницами для реалистичности
            time.sleep(2)

    if not results:
        print("\nNo data collected. Check Parser/result/errors.log")
        return

    df = pd.DataFrame(results)
    df.columns = ['Название', 'Цена', 'Количество_отзывов', 'Дата_доставки', 'Ссылка']
    df = df.sort_values(by='Цена')
    
    df.to_csv(result_file_txt, sep=';', index=False, encoding='utf-8')
    df.to_excel(result_file_xlsx, index=False)
            
    print(f"\nSuccess! Results saved to result/ folder.")

if __name__ == "__main__":
    main()
