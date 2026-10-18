#!/usr/bin/env bash
# ------------------------------------------------------------
# File: alias.sh
# ------------------------------------------------------------


LOSEMUL=$(mth "1 + (1 / ($payout - 1)) + (0.05 / $payout)" 4 d)
# -- custom flag 
d-start_help(){
	echo "usage: 
	d-start 
	-g|--global <start_balance> <basebet> <winchance> <losemul>
	-m|--mode <mode> 
	-st|--stop <upper_balance> <lower_balance>
	-w|--wager <basebet> <bet_pct> <winchance>
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
			-w|--wager) 
			    export WAGER_BASE_BET="${2}"
				export WAGER_BET_PCT="${3}"
				export WAGER_WIN_CHANCE="${4}"
				shift 4
			    ;;	
			-st|--stop)
				export CUSTOM_UPPER_LIMIT_BALANCE="${2:-15.00000000}"
				export CUSTOM_LOWER_LIMIT_BALANCE="${3:-0.00000000}"
				shift 3
				;;
			-g|--global)
				export START_BALANCE="${2:-5.00000000}"
				export GLOBAL_BASE_BET="${3:-0.01}"
				export GLOBAL_WIN_CHANCE="${4:-0.5}"
				export GLOBAL_MULTI="${5:-}"
				shift 5
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
