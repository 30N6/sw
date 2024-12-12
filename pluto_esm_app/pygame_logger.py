import sys, os
import pygame

def main():
  screen_size = (1280, 800)

  pygame.init()
  surface = pygame.display.set_mode(screen_size)

  running = True
  while (running):
    for i in pygame.event.get():
      if i.type == pygame.QUIT:
        running = False
      elif i.type == pygame.KEYDOWN:
        print(i.key)

if __name__ == "__main__":
  main()
  sys.exit(0)
