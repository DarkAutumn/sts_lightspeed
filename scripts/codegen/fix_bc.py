import sys
import re

with open('src/combat/BattleContext.cpp', 'r') as f:
    content = f.read()

content = content.replace('Action([](BattleContext &b)', 'Action([&](BattleContext &b)')
content = content.replace('Action([=](BattleContext &b)', 'Action([&](BattleContext &b)')
content = content.replace('b.attackEnemy(t, dmg);', 'b.monsters.arr[t].attacked(b, dmg);')

with open('src/combat/BattleContext.cpp', 'w') as f:
    f.write(content)
print("done")
