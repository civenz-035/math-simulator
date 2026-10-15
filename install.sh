#!/usr/bin/env bash
echo "no need to install just check dependency"

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
deps_path="${script_dir}/check-deps.sh"
alias_path="${script_dir}/lib/alias.sh"

# -- alias and deps check add to rcfiles
rc_files=(".bashrc" ".zshrc")
source_marker="# Added by simulator install script"
quoted_alias_path="'${alias_path//\'/\'\\\'\'}'"
source_line="[[ -f ${quoted_alias_path} ]] && source ${quoted_alias_path}"
count=0

for rc__ in "${rc_files[@]}"; do
    rc_file="$HOME/$rc__"

    # Ignore missing profiles; -e follows a valid symlink to its target.
    [[ -e "$rc_file" ]] || continue
    count=$((count + 1))

    echo "กำลังตรวจสอบไฟล์ config: $rc_file"
    if grep -Fq "$source_marker" "$rc_file" 2>/dev/null; then
        echo "alias source already present in $rc_file"
        continue
    fi

    {
        printf '\n%s\n' "$source_marker"
        printf '%s\n' "$source_line"
    } >> "$rc_file"
    echo "เพิ่ม alias source ใน $rc_file แล้ว"
done

echo "$count source file found"

# รันสคริปต์เช็ค dependency ต่อ
if [[ -f "$deps_path" ]]; then
    bash "$deps_path"
else
    echo "ไม่พบไฟล์เช็ค dependencies ที่: $deps_path"
fi
