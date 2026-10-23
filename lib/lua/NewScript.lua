base = 0.0005
mul=1.01
----------Chance Settings---------- 
chance = 1
atC    = false
minC   = 0.8
maxC   = 1
rcW    = true

function CalculateBet()
	if Win then
		NextBet=base
		NextBet.High=NextBet.High
	else
		NextBet.Amount=PreviousBet.TotalAmount*mul
	end
end

function Reset()
	if atC == true then
		NextBet.Chance= math.random(minC*100,maxC*100)/100 
	else
		NextBet.Chance=Chance
	end
		NextBet.Amount=base
		NextBet.High=true
end