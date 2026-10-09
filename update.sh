#!/usr/bin/env bash
# ------------------------------------------------------------
# File: update.sh
# ------------------------------------------------------------
maths_dir="$(dirname $0)/lib"
# -- update the maths.sh lib    
if [[ -f "$HOME/.maths-helper/maths.sh" ]]; then
    cp "$HOME/.maths-helper/maths.sh" "$maths_dir"
    echo "#updated $(date +'%Y-%m-%d %H:%M:%S')" | tee -a "$maths_dir/maths.sh"    
    echo "maths.sh updated"    
else
    echo "maths.th not found"
    source $HOME/.bashrc &&
    gclone mhp &&
    g -sim--update &&
    echo "simulator's maths lib updated"    
fi

