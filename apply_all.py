def combine_files(filenames):
    content = []
    for f in filenames:
        with open(f, 'r') as file:
            content.append(file.read())
    return '\n'.join(content)

attacks_code = combine_files(['silent_attacks.cpp', 'defect_attacks.cpp'])
skills_code = combine_files(['silent_skills1.cpp', 'silent_skills2.cpp', 'defect_skills.cpp'])
powers_code = combine_files(['silent_powers.cpp', 'defect_powers.cpp'])

# Add BACKSTAB to attacks
backstab_str = """
        case CardId::BACKSTAB: {
            const int dmg = calculateCardDamage(c, t, up ? 15 : 11);
            addToBot( Actions::AttackEnemy(t, dmg) );
            break;
        }
"""
attacks_code += backstab_str

with open('src/combat/BattleContext.cpp', 'r') as f:
    cpp_code = f.read()

target = '        default:\n#ifdef sts_asserts'
parts = cpp_code.split(target)

if len(parts) >= 4:
    # parts[0] is before first default (Attack)
    # parts[1] is between first and second default (Skill)
    # parts[2] is between second and third default (Power)
    
    new_code = parts[0] + attacks_code + '\n' + target + parts[1] + skills_code + '\n' + target + parts[2] + powers_code + '\n' + target
    
    # Add the remaining parts back
    for i in range(3, len(parts)):
        new_code += parts[i]
        if i < len(parts) - 1:
            new_code += target

    with open('src/combat/BattleContext.cpp', 'w') as f:
        f.write(new_code)
    print("Injected Silent and Defect cards into BattleContext.cpp successfully.")
else:
    print(f"Error: expected at least 4 occurrences of target, found {len(parts) - 1}")
