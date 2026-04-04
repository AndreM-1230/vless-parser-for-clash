import urllib.parse
import yaml
import requests
import sys
import re
import os

SOURCES = {
    "my_vless_list": "https://raw.githubusercontent.com/.../links.txt",
    "finland_nodes": "https://provider.com/config/"
}

OUTPUT_DIR = "./proxies_out"

def parse_vless(vless_url):
    try:
        parsed = urllib.parse.urlparse(vless_url.strip())
        if parsed.scheme != "vless":
            return None

        params = urllib.parse.parse_qs(parsed.query)
        server = parsed.hostname
        port = parsed.port or 443

        proxy = {
            "name": urllib.parse.unquote(parsed.fragment) if parsed.fragment else f"VLESS-{server}",
            "type": "vless",
            "server": server,
            "port": int(port),
            "uuid": parsed.username,
            "network": params.get("type", ["tcp"])[0],
            "tls": params.get("security", [""])[0] == "tls" or params.get("security", [""])[0] == "reality",
            "udp": True
        }

        if params.get("security", [""])[0] == "reality":
            proxy["reality-opts"] = {
                "public-key": params.get("pbk", [""])[0],
                "short-id": params.get("sid", [""])[0]
            }
            proxy["servername"] = params.get("sni", [server])[0]
            proxy["flow"] = params.get("flow", [""])[0]
            proxy["client-fingerprint"] = params.get("fp", ["chrome"])[0]

        if proxy["network"] == "ws":
            proxy["ws-opts"] = {
                "path": params.get("path", ["/"])[0],
                "headers": { "Host": params.get("sni", [server])[0] }
            }
            
        return proxy
    except Exception as e:
        return None

def process_source(name, url):
    print(f"--> Processing [{name}] from {url}...")
    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        links = re.findall(r'(vless://[^\s]+)', r.text)
        
        proxies = [parse_vless(l) for l in links if parse_vless(l)]
        
        if proxies:
            filename = os.path.join(OUTPUT_DIR, f"{name}.yml")
            with open(filename, 'w', encoding='utf-8') as f:
                yaml.dump({"proxies": proxies}, f, allow_unicode=True, sort_keys=False, default_flow_style=False, indent=2)
            print(f"    Done! Saved {len(proxies)} proxies to {filename}")
        else:
            print(f"    Warning: No VLESS links found for {name}")
            
    except Exception as e:
        print(f"    Error processing {name}: {e}")

def main():
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    for name, url in SOURCES.items():
        process_source(name, url)

if __name__ == "__main__":
    main()
