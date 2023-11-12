import pygame
import socket
import sys

class Network(object):
    
    def __init__(self):
        self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server = "192.168.1.254" # Fred = "192.168.1.254" # Bert = "192.168.1.7" # School = "192.168.104.48"
        self.port = 5555
        self.address = (self.server, self.port)
        self.id = self.connect()
        print(self.id)
        
    def connect(self):
        try:
            self.client.connect(self.address)
            return self.client.recv(2048).decode()
            
        except (socket.error, socket.timeout) as e:
            print(f"Error in connecting: {e}")
        
    def send(self, data):
        try:
            self.client.send(str.encode(data))
            return self.client.recv(80000).decode()
        except (socket.error, socket.timeout) as e:
            print("Error:", e)

class mainSprite(pygame.sprite.Sprite):

    playerColours = ((255,0,0), (0,0,255), (0,255,0), (255,255,0))

    def __init__(self, playerNo, fadeAmount, x, y, width, height):
        super().__init__()
        self.playerNo = playerNo
        self.fadeAmount = fadeAmount
        self.image = pygame.Surface([width,height])
        self.calcColour()
        self.image.fill(self.colour)
        self.rect = self.image.get_rect()
        self.rect.centerx = x
        self.rect.centery = y

    def draw(self, surface):
        self.calcColour()
        self.image.fill(self.colour)
        surface.blit(self.image, (self.rect.x, self.rect.y))

    def calcColour(self):
        first = mainSprite.playerColours[self.playerNo][0] + self.fadeAmount * (127.5-mainSprite.playerColours[self.playerNo][0]) / 60
        second = mainSprite.playerColours[self.playerNo][1] + self.fadeAmount * (127.5-mainSprite.playerColours[self.playerNo][1]) / 60
        third = mainSprite.playerColours[self.playerNo][2] + self.fadeAmount * (127.5-mainSprite.playerColours[self.playerNo][2]) / 60

        self.colour = (first, second, third)


def main():
    screen = pygame.display.set_mode((404,404))
    pygame.display.set_caption("Client Window")
    screen.fill((127.5,127.5,127.5))

    clock = pygame.time.Clock()
    pygame.display.flip()
    
    n = Network()
    n.client.settimeout(5)
    print(n.send("Create Player"))

    running = True

    left = True
    right = True
    up = True
    down = True

    missingDataMessagePrinted = False
    noDataMessagePrinted = False

    oldSpriteGroup = pygame.sprite.Group()
    previousKnownLocations = {}

    currentFades = {}

    while running:
        clock.tick(60)

        try:
            drawData = n.send("Data")
        except socket.timeout:
            drawData = None
        
        if drawData is None:
            if not missingDataMessagePrinted:
                print("Data not recieved, waiting for reconnection...")
                missingDataMessagePrinted = True
        elif drawData == "N/A":
            if not noDataMessagePrinted:
                print("No available data")
                noDataMessagePrinted = True
        else:
            missingDataMessagePrinted = False
            noDataMessagePrinted = False

            newSpriteGroup = pygame.sprite.Group()

            for element in drawData.split(";"):
                currentObjectData = element.split(",")
                playerNo, fadeAmount, x, y, width, height = int(currentObjectData[0]), int(currentObjectData[1]), \
                    int(currentObjectData[2]), int(currentObjectData[3]), int(currentObjectData[4]), int(currentObjectData[5])

                print(currentFades)
                currentFades[playerNo] = fadeAmount
                print(currentFades)

                newSpriteGroup.add(mainSprite(playerNo, fadeAmount, x, y, width, height))
                if previousKnownLocations.get(playerNo) is not None:
                    currentY = (y//4)*4 + 2
                    currentX = (x//4)*4 + 2
                    tempX = currentX
                    tempY = currentY
                    prevX, prevY = previousKnownLocations[playerNo]

                    sign = lambda a: 1 if a>0 else -1 if a<0 else 0 # Not mine, thanks to https://www.quora.com/How-do-I-get-sign-of-integer-in-Python, specifically Guarav Jain's answer
                    
                    directionSign = sign(currentY-prevY)

                    while directionSign*tempY > directionSign*prevY:
                        oldSpriteGroup.add(mainSprite(playerNo, fadeAmount, tempX, tempY, 4, 4))
                        tempY -= 4*directionSign

                    directionSign = sign(currentX-prevX)

                    while directionSign*tempX > directionSign*prevX:
                        oldSpriteGroup.add(mainSprite(playerNo, fadeAmount, tempX, tempY, 4, 4))
                        tempX -= 4*directionSign
                else:
                    oldSpriteGroup.add(mainSprite(playerNo, fadeAmount, x, y, 4, 4))
                previousKnownLocations[playerNo] = (x, y)
                

            screen.fill((127.5,127.5,127.5))

            for sprite in newSpriteGroup:
                sprite.draw(screen)

            spriteCounter = 0
            for sprite in oldSpriteGroup:
                spriteCounter += 1
                print(sprite.fadeAmount)
                sprite.fadeAmount = currentFades[sprite.playerNo]
                print(currentFades[sprite.playerNo], sprite.fadeAmount)
                sprite.draw(screen)

            pygame.display.update()


            for sprite in newSpriteGroup:
                sprite.kill()


        keys = pygame.key.get_pressed()

        if keys[pygame.K_LEFT] and left:
            left = False
            print(n.send("Left"))
        elif not keys[pygame.K_LEFT]:
            left = True

        if keys[pygame.K_RIGHT] and right:
            right = False
            print(n.send("Right"))
        elif not keys[pygame.K_RIGHT]:
            right = True

        if keys[pygame.K_UP] and up:
            up = False
            print(n.send("Up"))
        elif not keys[pygame.K_UP]:
            up = True

        if keys[pygame.K_DOWN] and down:
            down = False
            print(n.send("Down"))
        elif not keys[pygame.K_DOWN]:
            down = True
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
    
    print(n.send("Disconnect"))
    pygame.quit()
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
    
