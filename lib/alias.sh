#!/usr/bin/env bash
# ------------------------------------------------------------
# File: alias.sh
# ------------------------------------------------------------


alias dpy='d -py'
LOSEMUL=$(mth "1 + (1 / ($payout - 1)) + (0.05 / $payout)" 4 d)
# -- custom flag 
d-start(){
	local cmd="dpy"

	while (( $# > 0 )); do
		case "$1" in
			-m4|--mode4) 
				GAME_MODE='4'
				# พื้นฐานของ Custom (ถ้าปล่อยว่าง จะใช้ GLOBAL_xxx)
				CUSTOM_BASE_BET="${2:-0.01}"
				CUSTOM_WIN_CHANCE="${3:-0.5}"
				#CUSTOM_BET_TARGET=high
				
				# Multiplier Settings (On Loss)
				CUSTOM_LOSS_MUL="${4:-$LOSEMUL}"
				shift 4
			    ;;
			-m4---upbal)
			
				CUSTOM_UPPER_LIMIT_BALANCE="${2:-15.00000000}"
				CUSTOM_LOWER_LIMIT_BALANCE="${3:-0.00000000}"
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
		d -py 		

}

