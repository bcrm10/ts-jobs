#!/usr/bin/env python3
"""
Scraper de ofertas de Trabajador/a Social en Chile.
Se ejecuta via GitHub Actions una vez al día.
Guarda resultados en jobs.json que la app lee directamente.
"""
import requests
from bs4 import BeautifulSoup
import json
import time
import re
from datetime import datetime, timezone

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'es-CL,es;q=0.9',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
}

def scrape_computrabajo():
    """Scrape CompuTrabajo Chile - el portal con más ofertas de TS en Chile"""
    jobs = []
    queries = [
        'trabajador-social',
        'asistente-social',
        'dupla-psicosocial',
        'gestor-social',
        'coordinador-social',
    ]
    
    for query in queries:
        try:
            url = f'https://cl.computrabajo.com/trabajos-de-{query}'
            resp = requests.get(url, headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                print(f"  CT {query}: status {resp.status_code}")
                continue
            
            soup = BeautifulSoup(resp.text, 'lxml')
            articles = soup.find_all('article', {'class': re.compile('js-o-li')})
            
            if not articles:
                # Try alternate selector
                articles = soup.find_all('article', {'class': 'box_offer'})
            
            for art in articles[:20]:
                try:
                    # Title
                    title_el = art.find('h2') or art.find('a', {'class': re.compile('js-o-link')})
                    title = title_el.get_text(strip=True) if title_el else ''
                    if not title:
                        continue
                    
                    # Link
                    link_el = art.find('a', href=True)
                    link = ''
                    if link_el:
                        href = link_el['href']
                        link = href if href.startswith('http') else 'https://cl.computrabajo.com' + href
                    
                    # Company
                    comp_el = art.find('a', {'class': re.compile('fc_base')}) or art.find('p', {'class': re.compile('fs16')})
                    company = comp_el.get_text(strip=True) if comp_el else ''
                    
                    # City
                    city_el = art.find('span', {'class': re.compile('fc_aux')})
                    city = city_el.get_text(strip=True) if city_el else 'Chile'
                    
                    # Date
                    date_el = art.find('time') or art.find('span', {'class': re.compile('date|fecha|time')})
                    date_str = ''
                    if date_el:
                        date_str = date_el.get('datetime', '') or date_el.get_text(strip=True)
                    
                    jobs.append({
                        'title': title,
                        'org': company,
                        'city': city,
                        'date': date_str,
                        'link': link,
                        'source': 'CompuTrabajo'
                    })
                except Exception as e:
                    continue
            
            print(f"  CT {query}: {len(articles)} items")
            time.sleep(1.5)
            
        except Exception as e:
            print(f"  CT {query} error: {e}")
    
    return jobs


def scrape_trabajando():
    """Scrape Trabajando.com Chile"""
    jobs = []
    queries = ['trabajador+social', 'asistente+social']
    
    for query in queries:
        try:
            url = f'https://www.trabajando.com/empleo?q={query}&l=Chile'
            resp = requests.get(url, headers=HEADERS, timeout=15)
            if resp.status_code != 200:
                print(f"  TRB {query}: status {resp.status_code}")
                continue
            
            soup = BeautifulSoup(resp.text, 'lxml')
            
            # Trabajando.com structure
            cards = soup.find_all('div', {'class': re.compile('job-card|oferta|vacancy')})
            
            for card in cards[:15]:
                try:
                    title_el = card.find(['h2', 'h3', 'a'], {'class': re.compile('title|cargo|name')})
                    if not title_el:
                        title_el = card.find('a')
                    title = title_el.get_text(strip=True) if title_el else ''
                    if not title or len(title) < 5:
                        continue
                    
                    link_el = card.find('a', href=True)
                    link = ''
                    if link_el:
                        href = link_el['href']
                        link = href if href.startswith('http') else 'https://www.trabajando.com' + href
                    
                    company_el = card.find(['span', 'p', 'div'], {'class': re.compile('company|empresa|org')})
                    company = company_el.get_text(strip=True) if company_el else ''
                    
                    city_el = card.find(['span', 'p'], {'class': re.compile('city|ciudad|location|loc')})
                    city = city_el.get_text(strip=True) if city_el else 'Chile'
                    
                    jobs.append({
                        'title': title,
                        'org': company,
                        'city': city,
                        'date': '',
                        'link': link,
                        'source': 'Trabajando'
                    })
                except:
                    continue
            
            print(f"  TRB {query}: {len(cards)} items")
            time.sleep(2)
            
        except Exception as e:
            print(f"  TRB {query} error: {e}")
    
    return jobs


def deduplicate(jobs):
    seen = set()
    result = []
    for j in jobs:
        key = j['title'].lower().strip()[:50]
        if key not in seen and len(key) > 3:
            seen.add(key)
            result.append(j)
    return result


def main():
    print("=== Scraping ofertas TS Chile ===")
    print(f"Fecha: {datetime.now(timezone.utc).isoformat()}")
    
    all_jobs = []
    
    print("\n[CompuTrabajo]")
    ct_jobs = scrape_computrabajo()
    all_jobs.extend(ct_jobs)
    print(f"  Total: {len(ct_jobs)}")
    
    print("\n[Trabajando.com]")
    trb_jobs = scrape_trabajando()
    all_jobs.extend(trb_jobs)
    print(f"  Total: {len(trb_jobs)}")
    
    # Deduplicar
    all_jobs = deduplicate(all_jobs)
    
    # Guardar
    output = {
        'updated_at': datetime.now(timezone.utc).isoformat(),
        'total': len(all_jobs),
        'jobs': all_jobs
    }
    
    with open('jobs.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ Guardadas {len(all_jobs)} ofertas únicas en jobs.json")


if __name__ == '__main__':
    main()
