#!/usr/bin/env bash
# ------------------------------------------------------------
# File: alias.sh
# ------------------------------------------------------------


# -- custom flag 
d-start_help(){
	echo "usage: 
	d-start 
	-h|--help           แสดงวิธีใช้
	-mc|--mode-conf <mode 1-5>
	-wm|--wager-conf <basebet> <bet_pct %> <winchance%>
	-st|--stop-conf <upper_balance> <lower_balance>
	-gc|--global-conf <start_balance> <lose.mul> <basebet> <winchance%>
	ระบุ flag เหล่านี้เป็นชุด ๆ ได้ แล้วส่งส่วนที่เหลือต่อให้ simulator
	"
	
}
d-start(){


	while (( $# > 0 )); do
		case "$1" in
			-mc|--mode-conf) 
			    export GAME_MODE="${2}";
				shift 2
			    ;;
			-wm|--wager-conf) 
			  export WAGER_BASE_BET="${2}";
				export WAGER_BET_PCT="${3}";
				export WAGER_WIN_CHANCE="${4}";
				shift 4
			    ;;	
			-st|--stop-conf)
				export CUSTOM_UPPER_LIMIT_BALANCE="$2";
				export CUSTOM_LOWER_LIMIT_BALANCE="$3"
				shift 3
				;;
			-gc|--global-conf)
				export START_BALANCE="$2";
				export GLOBAL_LOSS_MUL="$3"
				export GLOBAL_BASE_BET="$4";
				export GLOBAL_WIN_CHANCE="$5";
				shift 5
				;;	
		
			*) 
				break ;
				;;
	  esac
	done
	case "$1" in
			-h|--help)
				d-start_help;
				return 0
				;;
	esac
		d -py "$@"		

}

alias dst='d-start'

# -- เมนูควบคุมแบบกดเลข (รู้ามาจากตำแหน่ง auto-resolve ทั้ง bash/zsh) --
if [[ -n "${ZSH_VERSION:-}" ]]; then
	_alias_sh="${(%):-%x}"
else
	_alias_sh="${BASH_SOURCE[0]:-$0}"
fi
_alias_sh_dir="$(cd -- "$(dirname -- "${_alias_sh}")" && pwd)"
dmenu(){ "$_alias_sh_dir/../bin/menu.sh" "$@"; }
alias dmn='dmenu' 
alias dcfpc='micro $simulator/config/dice.env'
