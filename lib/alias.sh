#!/usr/bin/env bash
# ------------------------------------------------------------
# File: alias.sh
# ------------------------------------------------------------


LOSEMUL=$(mth "1 + (1 / ($payout - 1)) + (0.05 / $payout)" 4 d)
# -- custom flag 
d-start_help(){
	echo "usage: 
	d-start 
	-g|--global <basebet> <winchance> <losemul>
	-m|--mode <mode> 
	-st --stop <stop loss>
	"
}
d-start(){
	local cmd="dpy"

	while (( $# > 0 )); do
		case "$1" in
			-m|--mode) 
			    export GAME_MODE="${2}"
				shift 2
			    ;;
			-st|--stop)
				export CUSTOM_UPPER_LIMIT_BALANCE="${2:-15.00000000}"
				export CUSTOM_LOWER_LIMIT_BALANCE="${3:-0.00000000}"
				shift 3
				;;
			-g|--global)
				export GLOBAL_BASE_BET="${2:-0.01}"
				export GLOBAL_WIN_CHANCE="${3:-0.5}"
				export GLOBAL_MULTI="${4:-1.006}"
				shift 4
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
