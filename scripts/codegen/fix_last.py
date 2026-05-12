import sys
import re

files = [
    'silent_attacks.cpp',
    'silent_skills1.cpp',
    'silent_skills2.cpp',
    'silent_powers.cpp',
    'defect_attacks.cpp',
    'defect_skills.cpp',
    'defect_powers.cpp'
]

for f in files:
    try:
        with open(f, 'r') as file:
            content = file.read()
            
        # Regex replacements
        content = re.sub(r'        case CardId::(DEFEND_BLUE|WRAITH_FORM):(.*?)break;\n        \}', r'        // CardId::\1 is defined natively in STS lightspeed', content, flags=re.DOTALL)
        
        # In case WRAITH_FORM is just case CardId::WRAITH_FORM:\n without {}
        content = re.sub(r'        case CardId::WRAITH_FORM:[\s\S]*?break;\n', r'        // CardId::WRAITH_FORM is defined natively in STS lightspeed\n', content)
        
        with open(f, 'w') as file:
            file.write(content)
        print(f"Patched {f}")
    except Exception as e:
        print(f"Error on {f}: {e}")

print("Fixes applied.")
