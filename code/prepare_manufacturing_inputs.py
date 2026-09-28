"""Download published source workbooks and rebuild manufacturing parameters."""
from pathlib import Path
import hashlib,json,subprocess,sys,urllib.request,zipfile

ROOT=Path(__file__).resolve().parents[1]

def main():
    out=ROOT/'input/literature';out.mkdir(parents=True,exist_ok=True)
    (ROOT/'output/checks').mkdir(parents=True,exist_ok=True)
    sources=json.loads((ROOT/'input/manufacturing_sources.json').read_text())
    for item in sources:
        path=out/item['file']
        if path.exists():data=path.read_bytes()
        elif 'archive' in item:
            with zipfile.ZipFile(out/item['archive']) as archive:
                matches=[n for n in archive.namelist() if n.lower().endswith('.xlsx') and hashlib.sha256(archive.read(n)).hexdigest()==item['sha256']]
                if len(matches)!=1:raise ValueError('Cannot identify the Table S14 workbook by its recorded hash')
                data=archive.read(matches[0])
        else:
            request=urllib.request.Request(item['url'],headers={'User-Agent':'PV-WRF-reproducibility'})
            with urllib.request.urlopen(request,timeout=60) as response:data=response.read()
        if hashlib.sha256(data).hexdigest()!=item['sha256']:raise ValueError('Source hash mismatch: '+item['file'])
        path.write_bytes(data)
    for name in ['extract_manufacturing.py','calibrate_inputs.py']:
        subprocess.run([sys.executable,str(ROOT/'code'/name)],cwd=ROOT,check=True)

if __name__=='__main__':main()
