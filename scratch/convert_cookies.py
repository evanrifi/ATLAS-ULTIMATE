import json
import os

def convert_json_to_netscape(json_file, output_file):
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            cookies = json.load(f)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("# Netscape HTTP Cookie File\n")
            f.write("# http://curl.haxx.se/rfc/cookie_spec.html\n")
            f.write("# This is a generated file!  Do not edit.\n\n")
            
            for cookie in cookies:
                domain = cookie.get('domain', '')
                # Netscape format requires leading dot for domains
                if not domain.startswith('.') and not domain.count('.') == 1:
                    domain = '.' + domain
                    
                # flag - TRUE/FALSE if all machines under given domain can access the cookie
                flag = "TRUE" if domain.startswith('.') else "FALSE"
                
                path = cookie.get('path', '/')
                secure = "TRUE" if cookie.get('secure', False) else "FALSE"
                expiry = int(cookie.get('expirationDate', 0))
                name = cookie.get('name', '')
                value = cookie.get('value', '')
                
                f.write(f"{domain}\t{flag}\t{path}\t{secure}\t{expiry}\t{name}\t{value}\n")
        
        print(f"✅ Successfully created {output_file}")
    except Exception as e:
        print(f"❌ Error converting cookies: {e}")

if __name__ == "__main__":
    # If you have the JSON file, put its name here. 
    # Otherwise, you can paste the JSON into a file named 'youtube_cookies.json'
    if os.path.exists('youtube_cookies.json'):
        convert_json_to_netscape('youtube_cookies.json', 'cookies.txt')
    else:
        print("❌ File 'youtube_cookies.json' not found. Please create it and paste your JSON there.")
