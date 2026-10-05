"""Download the original public Olist release; no credentials are stored."""
from pathlib import Path
import hashlib
import json
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
URL = 'https://www.kaggle.com/api/v1/datasets/download/olistbr/brazilian-ecommerce'
FILES = ['olist_orders_dataset.csv', 'olist_order_items_dataset.csv',
         'olist_order_reviews_dataset.csv', 'olist_customers_dataset.csv',
         'olist_products_dataset.csv', 'olist_sellers_dataset.csv',
         'product_category_name_translation.csv']

def main():
    folder = ROOT / 'data/raw'
    folder.mkdir(parents=True, exist_ok=True)
    archive = folder / 'olist.zip'
    if not all((folder / f).exists() for f in FILES):
        print('Downloading original public dataset from Kaggle...', flush=True)
        request = urllib.request.Request(URL, headers={'User-Agent': 'PromiseIntegrity/1.0'})
        with urllib.request.urlopen(request, timeout=180) as response, archive.open('wb') as out:
            while chunk := response.read(1024 * 1024):
                out.write(chunk)
        if not zipfile.is_zipfile(archive):
            raise RuntimeError('Kaggle did not return a ZIP. Download the dataset manually from its source page into data/raw.')
        with zipfile.ZipFile(archive) as z:
            for filename in FILES:
                matches = [n for n in z.namelist() if Path(n).name == filename]
                if len(matches) != 1:
                    raise ValueError(f'Expected exactly one {filename} in archive')
                (folder / filename).write_bytes(z.read(matches[0]))
        archive.unlink()
    manifest = {'source': URL, 'source_page': 'https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce',
                'license': 'CC BY-NC-SA 4.0', 'files': {f: hashlib.sha256((folder/f).read_bytes()).hexdigest() for f in FILES}}
    (folder / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print('Verified files:', ', '.join(FILES))

if __name__ == '__main__':
    main()
