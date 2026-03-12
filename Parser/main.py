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
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            'Accept': '*/*',
            'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
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
            api_url = f"https://card.wb.ru/cards/v1/detail?appType=1&curr=rub&dest=-1257786&spp=30&nm={sku}"
            
            response = requests.get(api_url, headers=self.headers, timeout=10)
            response.raise_for_status()
            data = response.json()

            products = data.get('data', {}).get('products', [])
            if not products:
                logging.error(f"No product data found for SKU: {sku}")
                return None

            p = products[0]
            
            title = p.get('name', 'Не указано')
            final_price = p.get('salePriceU', 0) // 100
            reviews = p.get('feedbacks', 0)
            delivery_date = "Доступно" if p.get('totalQuantity', 0) > 0 else "Нет в наличии"

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

    if not results:
        print("No data collected.")
        return

    df = pd.DataFrame(results)
    df.columns = ['Название', 'Цена', 'Количество_отзывов', 'Дата_доставки', 'Ссылка']
    df = df.sort_values(by='Цена')

    df.to_csv(result_file_txt, sep=';', index=False, encoding='utf-8')
    df.to_excel(result_file_xlsx, index=False)
            
    print(f"\nSuccess! Results saved to:\n - {result_file_txt}\n - {result_file_xlsx}")

if __name__ == "__main__":
    main()
