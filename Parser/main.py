import os
import re
import requests
import pandas as pd
import logging
from typing import List, Dict, Optional

class WBParserAPI:
    def __init__(self, result_dir: str):
        self.result_dir = result_dir
        os.makedirs(self.result_dir, exist_ok=True)
        logging.basicConfig(
            filename=os.path.join(self.result_dir, 'errors.log'),
            level=logging.ERROR,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        # Актуальные заголовки для обхода базовых проверок WB в 2026 году
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36',
            'Accept': '*/*',
            'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
            'Referer': 'https://www.wildberries.ru/',
            'Origin': 'https://www.wildberries.ru',
            'Accept-Encoding': 'gzip, deflate, br',
            'x-client-name': 'web'
        }

    def extract_sku(self, url: str) -> Optional[str]:
        match = re.search(r'catalog/(\d+)/detail', url)
        if match:
            return match.group(1)
        return None

    def parse_product(self, url: str) -> Optional[Dict]:
        sku = self.extract_sku(url)
        if not sku:
            logging.error(f"Could not extract SKU from URL: {url}")
            return None

        try:
            # Используем версию v2 и стандартные параметры для Москвы (-1257786)
            api_url = f"https://card.wb.ru/cards/v2/detail?appType=1&curr=rub&dest=-1257786&spp=30&nm={sku}"
            
            response = requests.get(api_url, headers=self.headers, timeout=10)
            
            if response.status_code == 429:
                logging.error(f"Rate limited (429) for SKU {sku}. Try using a proxy.")
                return None
            elif response.status_code == 498:
                logging.error(f"Anti-bot Challenge (498) triggered for SKU {sku}. WBAAS protection active.")
                return None
                
            response.raise_for_status()
            data = response.json()

            products = data.get('data', {}).get('products', [])
            if not products:
                logging.error(f"No product data found for SKU: {sku} (Status 200, but empty list)")
                return None

            p = products[0]
            
            title = p.get('name', 'Не указано')
            # В 2026 году цены могут приходить в salePriceU (в копейках)
            final_price = p.get('salePriceU', 0) // 100
            reviews = p.get('feedbacks', 0)
            # Расширенная проверка остатков
            total_qty = sum(size.get('stocks', [0])[0] if isinstance(size.get('stocks'), list) else 0 for size in p.get('sizes', []))
            delivery_date = "Доступно" if total_qty > 0 or p.get('totalQuantity', 0) > 0 else "Нет в наличии"

            return {
                'title': title,
                'final_price': final_price,
                'reviews': reviews,
                'delivery_date': delivery_date,
                'url': url
            }

        except Exception as e:
            logging.error(f"Error parsing {url} via API: {str(e)}")
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

    os.makedirs(os.path.join(base_dir, 'main_base'), exist_ok=True)
    os.makedirs(os.path.join(base_dir, 'compare_base'), exist_ok=True)
    os.makedirs(result_dir, exist_ok=True)

    main_links = read_links(main_link_file)
    compare_links = read_links(compare_link_file)
    all_links = main_links + compare_links
    
    if not all_links:
        print("No links found. Please fill the .txt files in main_base and compare_base.")
        return

    print(f"Starting API parser for {len(all_links)} links...")
    
    parser = WBParserAPI(result_dir)
    results = []

    for i, url in enumerate(all_links, 1):
        print(f"Processing {i}/{len(all_links)}: {url}")
        data = parser.parse_product(url)
        if data:
            results.append(data)
        else:
            print(f"  [!] Failed to get data for {url}. Check errors.log")

    if not results:
        print("\nNo data collected. Check Parser/result/errors.log for details.")
        print("Tip: If you see 498/429 errors, Wildberries is blocking your IP or requires JS challenge solving.")
        return

    df = pd.DataFrame(results)
    df.columns = ['Название', 'Цена', 'Количество_отзывов', 'Дата_доставки', 'Ссылка']
    df = df.sort_values(by='Цена')

    df.to_csv(result_file_txt, sep=';', index=False, encoding='utf-8')
    df.to_excel(result_file_xlsx, index=False)
            
    print(f"\nSuccess! Results saved to:\n - {result_file_txt}\n - {result_file_xlsx}")

if __name__ == "__main__":
    main()
