----------Chance Settings---------- 
atC    = true    ---[[ set Chance Auto = true  fix Manuel = false ]]--- 
minC   = 0.45 ---[[[ set Min Chance ]]]--- 
maxC   = 0.55 ---[[[ set Max Chance ]]]--- 
rcW    = true     ---[[[ random Chance if Wom ]]]--- 
rcL    = false     ---[[[ random Chance if Lost ]]]--- 
chance = 0.5     ---[[ set Chance if ChanecAoto fix Manual ]]--- 
   if atC == true then chance = math.random(minC*100,maxC*100)/100 end 
----------Base Settings----------- 
constant = 0
 ---[[[ set " 0 " if set base Manual ]]--- 
 base = 0.001
   if constant >= 0 then base = balance/constant end 
nextbet = base 
----------Multi---------- 
mulW    = 1     ---[[[ Multiple on win ]]]--- 
mulL    = 1.006      ---[[[ Multiple on Lost ]]]--- 
mulAuto = true     ---[[[ Auto set " true " /// Manual set " false" ]]]--- 
----------BetHigh---------- 
bethigh = true  ---[[[ true = bet high /// false = bet low ]]]--- 
   bhAuto = true ---[[[ change hi / low auto ]]]---[[[ true //ro// false ]]]--- 
      bhW = true     ---[[[ chance auto hi/low if win ]]]--- 
      bhL = false     ---[[[ change auto hi/low if lost ]]]--- 
----------Count---------- 
wc = 0 
lc = 0 
la = 0 
pf = 0 
----------Stop Settings---------- 
stBal = balance 
blTg  = 0.03 ---[[[ Stop if Balance // set " 0 " if not ]]]--- 
prfTg = 0     ---[[[ Stop if Profit  // set " 0 " if not ]]]--- 
stL   = 0     ---[[[ Stop if lost  // set " 0 " if not ]]]--- 
----------Reset to Base---------- 
rpf = 0.00000001   ---[[[ reset to base if profit ]]]--- 
rpfL = 0      ---[[[ reset to base if lost  /// set " 0 " if not ]]]--- 
rW = 1    ---[[[ reset to base if win? ]]]--- 
  del_W = false    ---[[[ reset lost amout to " 0 " ]]]---[[[ true //or// false]]]--- 
rL = 0     ---[[[ reset to base if lost? ]]]--- 
  del_L = false    ---[[[ reset lost amout to " 0 " ]]]---[[[ true //or// false]]]--- 
-------------------- 
function dobet () 
-------------------- 
---fx//stop--- 
if blTg > 0 then if balance >= blTg then stop() end end 
if prfTg > 0 then if (-pf) >= prfTg then stop() end end 
if stL > 0 then if pf >= stL then stop() end end 
-------------------- 
---[[[ Win ]]]--- 
if win then 
   ---Chance--- 
   if atC == true and rcW == true then 
      chance = math.random(minC*100,maxC*100)/100 
   end 
   ---BetHigh---- 
   if bhAuto == true and bhW == true then 
      if math.random(1,9)*math.random(1,9) >= 27 then 
         bethigh = true  else bethigh = false end 
   end 
   
   ---Count--- 
   wc += 1 
   lc = 0 
   la -= currentprofit 
   pf -= currentprofit 
   ---Nextbet--- 
   if mulAuto == true then mulW = chance/(97-chance)+1 end 
   nextbet = previousbet*mulW 
   ---Reset to Base--- 
   if rW > 0 and wc >= rW then 
      if del_W == true then 
         wc = 0 
         lc = 0 
         la = 0 
         if constant >= 0 then base = balance/constant end 
         nextbet = base 
       else 
         if constant >= 0 then base = balance/constant end 
        nextbet = base 
     end 
   end 
   if (-la) >= rpf then 
      wc = 0 
      lc = 0 
      la = 0 
      if constant >= 0 then base = balance/constant end 
      nextbet = base 
   end 
--------------------- 
---[[[ Lost ]]]--- 
 else 
   ---Chance--- 
   if atC == true and rcL == true then 
      chance = math.random(minC*100,maxC*100)/100 
   end 
    ---BetHigh---- 
   if bhAuto == true and bhL == true then 
      if math.random(1,9)*math.random(1,9) >= 27 then 
         bethigh = true  else bethigh = false end 
   end 
   ---Count--- 
   wc = 0 
   lc += 1 
   la += previousbet 
   pf += previousbet 
   ---Nextbet--- 
   if mulAuto == true then mulL = chance/(95-chance)+1 end 
   nextbet = previousbet*mulL 
   ---Reset to Base--- 
   if rL > 0 and lc >= rL then 
      if del_L == true then 
         wc = 0 
         lc = 0 
         la = 0 
         if constant >= 1 then base = balance/constant end 
         nextbet = base 
       else 
        if constant >= 1 then base = balance/constant end 
        nextbet = base 
     end 
   end 
end 
end