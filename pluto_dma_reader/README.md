cd /usr/local/bin
sudo wget http://releases.linaro.org/components/toolchain/binaries/7.2-2017.11/arm-linux-gnueabihf/gcc-linaro-7.2.1-2017.11-x86_64_arm-linux-gnueabihf.tar.xz
sudo tar -xf gcc-linaro-7.2.1-2017.11-i686_arm-linux-gnueabihf.tar.xz
export PATH=$PATH:/usr/local/bin/gcc-linaro-7.2.1-2017.11-i686_arm-linux-gnueabihf/bin
/usr/local/bin/gcc-linaro-7.2.1-2017.11-x86_64_arm-linux-gnueabihf/bin/arm-linux-gnueabihf-gcc --sysroot=$HOME/pluto-0.38.sysroot -std=gnu99 -g -o pluto_dma_reader pluto_dma_reader.c -lpthread -liio -lm -Wall -Wextra
