import urllib.parse
import yaml
import requests
import re
import os
import random
import socket

MAX_PROXIES = 80
TIMEOUT_SECONDS = 0.8

SOURCES = {
    "my_vless_list": {
        "links": [
            "https://raw.githubusercontent.com/.../links.txt",
            "https://raw.githubusercontent.com/.../links2.txt"
        ],
        "filter": False
    },
    "finland_nodes": {
        "links": [
            "https://provider.com/config/"
        ],
        "filter": True
    }
}

OUTPUT_DIR = "./proxies_out"

def is_alive(host, port):
    try:
        with socket.create_connection((host, port), timeout=TIMEOUT_SECONDS):
            return True
    except:
        return False

def clean_name(name):
    if not name: return "VLESS"
    name = urllib.parse.unquote(name)
    name = re.sub(r'[\x00-\x1F\x7F-\x9F]', '', name)
    name = re.sub(r'[^\x20-\x7Eа-яА-ЯёЁ\u2000-\u3000\u2700-\u27BF\U0001f300-\U0001f64f\U0001f680-\U0001f6ff]', '', name)
    return name.strip()[:100]

def parse_vless(url, apply_filter=True):
    try:
        parsed = urllib.parse.urlparse(url.strip())
        params = urllib.parse.parse_qs(parsed.query)
        host = parsed.hostname
        port = int(parsed.port or 443)
        security = params.get("security", [""])[0]
        sni = params.get("sni", [""])[0].lower()
        
        if apply_filter:
            bad_sni = {'google.com', 'facebook.com', 'microsoft.com', 'bing.com', 'yahoo.com'}
            if sni in bad_sni:
                return None
            cdn_ports = {80, 8080, 8880, 2052, 2082, 2086, 2095, 2053, 2083, 2087, 2096}
            if port in cdn_ports and security != "tls":
                return None

            if not is_alive(host, port):
                return None

        proxy = {
            "name": clean_name(parsed.fragment or f"VLESS-{host}"),
            "type": "vless",
            "server": host,
            "port": port,
            "uuid": parsed.username,
            "network": params.get("type", ["tcp"])[0],
            "tls": security in ["tls", "reality"],
            "udp": True,
            "cipher": "auto"
        }
        
        if security == "reality":
            proxy["reality-opts"] = {
                "public-key": params.get("pbk", [""])[0],
                "short-id": params.get("sid", [""])[0]
            }
            proxy["servername"] = params.get("sni", [host])[0]
            proxy["flow"] = params.get("flow", [""])[0]
            proxy["client-fingerprint"] = params.get("fp", ["chrome"])[0]

        if proxy["network"] == "ws":
            proxy["ws-opts"] = {"path": params.get("path", ["/"])[0], "headers": {"Host": host}}
            
        if proxy["network"] == "grpc":
            proxy["grpc-opts"] = {"grpc-service-name": params.get("serviceName", [""])[0]}

        return proxy
    except:
        return None

def main():
    if not os.path.exists(OUTPUT_DIR): os.makedirs(OUTPUT_DIR)

    for group_name, config in SOURCES.items():
        print(f"--> Группа [{group_name}]: фильтрация...")
        all_links = []
        should_filter = config.get("filter", True)
        
        for url in config["links"]:
            try:
                r = requests.get(url, timeout=10)
                all_links.extend(re.findall(r'(vless://[^\s#]+(?:#[^\s]*)?)', r.text))
            except: pass

        if not all_links: continue
        random.shuffle(all_links)

        reality_nodes = []
        other_nodes = []

        for l in all_links:
            p = parse_vless(l, apply_filter=should_filter)
            if p:
                if "reality-opts" in p:
                    reality_nodes.append(p)
                else:
                    other_nodes.append(p)
                
                if should_filter and len(reality_nodes) >= MAX_PROXIES:
                    break

        final_list = reality_nodes[:MAX_PROXIES]
        if len(final_list) < MAX_PROXIES:
            final_list.extend(other_nodes[:(MAX_PROXIES - len(final_list))])

        if final_list:
            path = os.path.join(OUTPUT_DIR, f"{group_name}.yml")
            yaml_content = yaml.dump({"proxies": final_list}, allow_unicode=True, sort_keys=False, indent=2, explicit_end=False)
            with open(path, 'w', encoding='utf-8') as f:
                f.write(yaml_content.strip() + '\n')
            print(f"--- Итог: {len(final_list)} прокси (Reality: {len(reality_nodes)}) сохранено.\n")

if __name__ == "__main__":
    main()