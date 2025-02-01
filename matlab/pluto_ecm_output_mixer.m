x = int64([27993, 30397]);
y = int64([-13367, 29906]);

ac = int32(x(1)) * int32(y(1))
bd = int32(x(2)) * int32(y(2))
ad = int32(x(1)) * int32(y(2))
bc = int32(x(2)) * int32(y(1))


re = x(1) * y(1) - x(2)*y(2)
im = x(1) * y(2) + x(2)*y(1)

dec2bin(re, 33)
dec2bin(im, 33)