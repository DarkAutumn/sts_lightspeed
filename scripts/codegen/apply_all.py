def combine_files(filenames):
    content = []
    for f in filenames:
        with open(f, 'r') as file:
            content.append(file.read())
    return '\n'.join(content)

attacks_code = combine_files(['watcher_attacks.cpp'])
skills_code = combine_files(['watcher_skills.cpp'])
powers_code = combine_files(['watcher_powers.cpp'])

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
    print("Injected Silent, Defect, and Watcher cards into BattleContext.cpp successfully.")
else:
    print(f"Error: expected at least 4 occurrences of target, found {len(parts) - 1}")
