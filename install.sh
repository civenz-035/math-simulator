#!/usr/bin/env bash
echo "no need to install just check dependency"

self_="$(dirname "$0")"
deps_path="${self_}/check-deps.sh"
alias_path="${self_}/lib/alias.sh"

# -- alias and deps check add to rcfiles
rc_files=(".bashrc" ".zshrc")
ins_rcf=""
count=0

for rc__ in "${rc_files[@]}"; do
    rc_="$HOME/$rc__"
    
    # เช็คว่าไฟล์มีตัวตนอยู่จริงไหม (ไม่ว่าจะเป้นไฟล์จริงหรือ symlink)
    if [[ -e "$rc_" ]]; then
        # เก็บ path เต็มๆ ไว้เลย ไม่ต้องใช้ readlink 
        # เพราะ cat >> จะวิ่งตาม symlink ไปเขียนที่ปลายทางให้อัตโนมัติครับ
        ins_rcf+="$rc_\n"
        (( count++ ))
    fi
done  

echo "$count source file found"

# ใช้ Here-String (<<<) แทน Pipe เพื่อเลี่ยง Subshell issue และอ่านตัวแปร ins_rcf
while IFS= read -r file; do
    [[ -z "$file" ]] && continue
    
    echo "กำลังตรวจสอบและเพิ่ม config ใน: $file"
    
    # เพิ่มเครื่องหมายปิด quote ให้ครบถ้วน
    cat >> "$file" << 'EOF'

# Added by simulator install script
[[ -f "$HOME/simulator/lib/alias.sh" ]] && source "$HOME/simulator/lib/alias.sh"
EOF
    
    echo "done wrote in $file"
done <<< "$ins_rcf"

# รันสคริปต์เช็ค dependency ต่อ
if [[ -f "$deps_path" ]]; then
    bash "$deps_path"
else
    echo "ไม่พบไฟล์เช็ค dependencies ที่: $deps_path"
fi
