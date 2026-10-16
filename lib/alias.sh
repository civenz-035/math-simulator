#!/usr/bin/env bash
# ------------------------------------------------------------
# File: alias.sh
# ------------------------------------------------------------


LOSEMUL=$(mth "1 + (1 / ($payout - 1)) + (0.05 / $payout)" 4 d)
# -- custom flag 
d-start_help(){
	echo "usage: 
	d-start 
	-m4|--mode <basebet> <winchance> <losemul>
	-m4--stop <stoop bal uper> <stop bal lower>
	"
}
d-start(){
	local cmd="dpy"

	while (( $# > 0 )); do
		case "$1" in
			-m4|--mode4) 
			  export GAME_MODE='4'
				# พื้นฐานของ Custom (ถ้าปล่อยว่าง จะใช้GLOBAL_xxx)
				export CUSTOM_BASE_BET="${2:-0.01}"
				export CUSTOM_WIN_CHANCE="${3:-0.5}"
				#CUSTOM_BET_TARGET=high
				
				# Multiplier Settings (On Loss)
				export CUSTOM_LOSS_MUL="${4:-$LOSEMUL}"
				shift 4
			    ;;
			-st|--stop)
			
				export CUSTOM_UPPER_LIMIT_BALANCE="${2:-15.00000000}"
				export CUSTOM_LOWER_LIMIT_BALANCE="${3:-0.00000000}"
				#CUSTOM_MIN_BET=0.00000000
				#CUSTOM_MAX_BET=0.00000000
				#CUSTOM_ZIGZAG_EVERY=0
				#CUSTOM_BETS_PER_SEC=0.00
				shift 3
				;;
		
			*) 
				
				break 
				;;
	   esac
	done
	case "$1" in
			-h|--help)
				d-start_help
				return 0
				;;
	esac
	
		d -py "$@"		

}

alias dst='d-start'
