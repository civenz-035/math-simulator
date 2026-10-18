#!/usr/bin/env bash
# ------------------------------------------------------------
# File: alias.sh
# ------------------------------------------------------------


LOSEMUL=$(mth "1 + (1 / ($payout - 1)) + (0.05 / $payout)" 4 d)
# -- custom flag 
d-start_help(){
	echo "usage: 
	d-start 
	-g|--global <start_balance> <lose.mul>  <basebet> <winchance%>
	-m|--mode <mode 1-5 > 
	-st|--stop <upper_balance> <lower_balance>
	-w|--wager <basebet> <bet_pct %> <winchance%>
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
