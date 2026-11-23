"""
Replace all em dashes (\u2014) across codebase with colons, commas, or periods as required by design rules.
"""
import os

em_dash = '\u2014'

def main():
    total_replaced = 0
    modified_files = []
    
    for root, dirs, files in os.walk('.'):
        if '.git' in root or '__pycache__' in root or '.pytest_cache' in root:
            continue
        for f in files:
            if f.endswith(('.py', '.html', '.js', '.css', '.md', '.json', '.txt', '.csv')):
                p = os.path.join(root, f)
                try:
                    with open(p, 'r', encoding='utf-8') as fh:
                        content = fh.read()
                    if em_dash in content:
                        count = content.count(em_dash)
                        # Replace ": " or ": " with ": " or ", "
                        new_content = content.replace(" " + em_dash + " ", ": ")
                        new_content = new_content.replace(em_dash + " ", ": ")
                        new_content = new_content.replace(" " + em_dash, ", ")
                        new_content = new_content.replace(em_dash, ": ")
                        
                        with open(p, 'w', encoding='utf-8') as fh:
                            fh.write(new_content)
                        total_replaced += count
                        modified_files.append((p, count))
                except Exception as e:
                    print(f"Error processing {p}: {e}")
                    
    print(f"Replaced {total_replaced} em dashes across {len(modified_files)} files.")
    for f, c in modified_files:
        print(f"  {f}: {c}")

if __name__ == "__main__":
    main()
