import pygame
import socket
import multiprocessing as mp # Far easier to type
import sys


'''CUSTOM PROCESSES'''

class ServerProcess(mp.Process):

    # Process for the server to receive connections

    def __init__(self, playerQueues, playerQsInUse, playerDataArray, trailDataArray, name=None):
        super().__init__(name=name)
        
        print("Server Process Initialising")
        
        # Initialises server

        self.server = "192.168.1.254" # Fred = "192.168.1.254" # Bert = "192.168.1.7" # School = "192.168.104.48"
        self.port = 5555
        
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setblocking(0)
        
        self.connectedClients = [] 
        self.clientProcesses = []
        
        self.running = True

        self.trailDataArray = trailDataArray

        self.playerDataArray = playerDataArray
        self.playerQueues = playerQueues
        self.playerQsInUse = playerQsInUse


    def run(self):

        print("Running")

        # Opens server to connections

        try:
            self.socket.bind((self.server, self.port))
            self.socket.settimeout(5)
            

        except socket.error as e:
            print(str(e))
        
        else:
            self.socket.listen(4)

            print("Server started, awaiting connection")

            while self.running:
                try:
                    connection, address = self.socket.accept() # Accept any incoming connections
                except socket.timeout:
                    pass
                else:
                    if not self.running:
                        connection.close()
                    else:
                        print(f"Connected to {address}")
    
                        self.connectedClients.append(ConnectedClient(connection, address))
    
                        self.clientProcesses.append(ClientProcess(self.connectedClients[-1], self.playerQueues, self.playerQsInUse,
                                                                 self.playerDataArray, self.trailDataArray, name=f"Client{len(self.connectedClients)}"))
                        self.clientProcesses[-1].start()
            
                        for clientProcess in self.clientProcesses:
                            if not clientProcess.is_alive():
                                index = self.clientProcesses.index(clientProcess)
                                self.connectedClients.pop(index)
                                self.clientProcesses.pop(index)

        finally:

            # Ends server no matter what

            print("Server shutting down...")
            try:
                self.stop()
            except Exception: # While normally this is terrible practice, this is ok in this context
                pass
            try:
                self.socket.close()
            except Exception: # See above comment
                pass

            socket.close()

    def stop(self):

        # Stops the server and disconnects all clients

        for process in self.clientProcesses:
            process.stop()

        self.running = False

class ClientProcess(mp.Process):

    # Handles a connected client

    def __init__(self, client, playerQueues, playerQsInUse, playerDataArray, trailDataArray, name=None):
        super().__init__(name=name)
        self.client = client
        self.running = True
        self.playerQueues = playerQueues
        self.playerQsInUse = playerQsInUse
        self.playerDataArray = playerDataArray

        self.isSpectator = True
        self.playerNo = None

    def run(self):
        
        self.client.connection.sendall(str.encode("Connected")) # Show the client has connected

        request = ""
        while self.running:
            try:

                data = self.client.connection.recv(2048) # Recieve data

                if not data: # End while loop once the client disconnects
                    break

                request = data.decode("utf-8")

                if request == "Data": # Send sprite data to client
                    self.playerDataArray._lock.acquire()
                    if self.playerDataArray[:].split('\x00')[0] == "":
                        self.client.connection.sendall(str.encode("N/A"))
                    else:
                        self.client.connection.sendall(str.encode(self.playerDataArray[:].split('\x00')[0]))
                    self.playerDataArray._lock.release()

                elif request == "Disconnect":
                    self.client.connection.sendall(str.encode("Disconnecting...")) # Disconnect client
                    self.client.playerQueue.put("Stop")
                    print(f"Disconnecting {self.client.address}")
                    break
                elif request == "Create Player": # Create the client's relative player
                    for index, inUse in enumerate(self.playerQsInUse):
                        if not inUse.value:
                            self.playerNo = index
                            break

                    if self.playerNo is None:
                        self.isSpectator = True
                        self.client.connection.send(str.encode("Spectator"))
                    else:
                        self.client.connection.send(str.encode(f"Created Player {self.playerNo+1}"))
                        self.client.playerQueue = self.playerQueues[self.playerNo]
                        self.client.playerQueue.put(request)
                else:
                    self.client.connection.sendall(str.encode(f"Executing request of {request}"))
                    self.client.playerQueue.put(request) # Pass unessential requests that do not require the client process to the main process
               
            except socket.timeout:
                pass

            except Exception as e:
                print("Error:", e)
                break
    
        print(f"Lost connection to {self.client.address}")

        try:
            self.client.playerQueue.put("Stop") # Delete the relevant player
        except Exception:
            pass

        self.client.connection.close()

    def stop(self):

        # Simply stops the running loop

        self.running = False


'''CLASSES'''

class ConnectedClient():

    # This Class holds one connected client's connection, address, and (if applicable) linked player's queue

    def __init__(self, connection, address):
        self.connection = connection
        self.address = address
        self.playerQueue = None

class TrailObject(pygame.sprite.Sprite):

    # Handles one individual part of a trail, just a sprite

    def __init__(self, playerNo, colour, x, y):
        super().__init__()
        self.playerNo = playerNo
        self.colour = colour
        self.image = pygame.Surface([4,4])
        self.image.fill(self.colour)
        self.rect = self.image.get_rect()
        self.rect.x = x
        self.rect.y = y

    def draw(self, surface):

        # Draws the sprite to a surface

        image = pygame.Surface([4,4])
        image.fill(self.colour)

        surface.blit(image, (self.rect.x, self.rect.y))

class Player(pygame.sprite.Sprite):

    obstacleTiles = []
    playerStats = (((255,0,0),12,8,4,198), ((0,0,255),12,8,384,198), ((0,255,0),8,12,198,4), ((255,255,0),8,12,198,384))

    # Main Player class for the game

    def __init__(self, playerNo, trailSpriteGroup):
        super().__init__()

        self.alive = True
        self.fullyDead = False
        
        self.playerNo = playerNo

        self.colour,self.width,self.height,x,y = Player.playerStats[self.playerNo]

        self.originalColour = self.colour

        self.upFacingHeight = 12
        self.upFacingWidth = 8

        self.rect = pygame.Rect(x,y,self.width,self.height)
        

        self.xVel = 0
        self.yVel = 0

        self.speed = 1
        
        self.turnRequests = mp.Queue(2)

        self.data = ""

        self.deathCounter = 0

        self.trailSpriteGroup = trailSpriteGroup
    
    def update(self):

        # Called every frame of the game, handles movement updates and turning
        
        if self.alive:

            self.rect.x += self.xVel
            self.rect.y += self.yVel

            if self.rect.x <= 0 or self.rect.x >= 404-self.width or self.rect.y <= 0 or self.rect.y >= 404-self.height \
                    or (self.rect.centerx // 4, self.rect.centery // 4) in Player.obstacleTiles:
                self.die()

            elif self.rect.centerx % 4 == 2 and self.rect.centery % 4 == 2: # Creates a "grid" in a way, allowing for easier collision detection and trail placement, 
                                                                            # note the player is in the middle of the square
            
                invalidTurn = True
            
                while invalidTurn and not self.turnRequests.empty():

                    currentTurn = self.turnRequests.get()

                    if currentTurn == "Left":
                        self.xVel = -1 * self.speed
                        self.yVel = 0
                        invalidTurn = False
                        self.height = self.upFacingWidth
                        self.width = self.upFacingHeight

                    elif currentTurn == "Right":
                        self.xVel = self.speed
                        self.yVel = 0
                        invalidTurn = False
                        self.height = self.upFacingWidth
                        self.width = self.upFacingHeight

                    elif currentTurn == "Up":
                        self.yVel = -1 * self.speed
                        self.xVel = 0
                        invalidTurn = False
                        self.height = self.upFacingHeight
                        self.width = self.upFacingWidth

                    elif currentTurn == "Down":
                        self.yVel = self.speed
                        self.xVel = 0
                        invalidTurn = False
                        self.height = self.upFacingHeight
                        self.width = self.upFacingWidth

            elif (self.rect.centerx // 4, self.rect.centery // 4) != ((self.rect.centerx - self.xVel) // 4, (self.rect.centery - self.yVel) // 4):
                Player.obstacleTiles.append(((self.rect.centerx - self.xVel) // 4, (self.rect.centery - self.yVel) // 4))
                self.trailSpriteGroup.add(TrailObject(self.playerNo, self.colour, (self.rect.centerx - self.xVel) // 4 * 4, (self.rect.centery - self.yVel) // 4 * 4))


        else:
            self.deathCounter += 1
            
            first = self.originalColour[0] + self.deathCounter * (127.5-self.originalColour[0]) / 60
            second = self.originalColour[1] + self.deathCounter * (127.5-self.originalColour[1]) / 60
            third = self.originalColour[2] + self.deathCounter * (127.5-self.originalColour[2]) / 60

            self.colour = (first, second, third)

            if self.deathCounter > 60:
                self.fullyDead = True

        
    def getData(self):

        # Returns and sets an attribute to a string of relevant data to send to clients

        self.data = ""

        dataTuple = (self.playerNo, self.deathCounter, self.rect.centerx, self.rect.centery, self.width, self.height)

        for index, item in enumerate(dataTuple):
            self.data += str(item)
            if index != len(dataTuple)-1:
                self.data += ","

        return self.data


    def draw(self, surface):

        # Draws the sprite to a surface

        image = pygame.Surface([self.width,self.height])
        image.fill(self.colour)

        surface.blit(image, (self.rect.centerx - self.width/2, self.rect.centery - self.height / 2))

    def die(self):
        
        # Kills the sprite, used when it hits something

        self.alive = False
        pygame.mixer.Sound.play(pygame.mixer.Sound(__file__.rsplit("\\",1)[0]+"\Audio\Death.wav"))

'''SUBROUTINES'''


'''MAIN'''

def main():

    pygame.mixer.init()

    playerQueues = [mp.Queue() for x in range(4)] # Holds intruction queues for each of the 4 players
    playerQsInUse = [mp.Value("i", False) for x in range(4)] # Holds if the above queues are in use, note that conversion between c_int and boolean is done automatically

    players = [None for x in range(4)] # Holds the actual player objects
    
    currentPlayerDataArray = mp.Array("u", 59) # Holds the current player data to be sent to the clients on request
    
    serverProcess = ServerProcess(playerQueues, playerQsInUse, currentPlayerDataArray, currentTrailDataArray, name = "Server") # Start the server process
    serverProcess.start()
    
    running = True
    
    clock = pygame.time.Clock()

    playerSpriteGroup = pygame.sprite.Group()
    trailSpriteGroup = pygame.sprite.Group()
    
    screen = pygame.display.set_mode((404,404)) # 404 because it makes an odd number of 4x4 "tiles" on each side, allowing for easy centering
    
    pygame.display.set_caption("Multiplayer Test")
    screen.fill((127.5,127.5,127.5))

    pygame.display.flip()

    while running:
        
        for index, queue in enumerate(playerQueues): # Parse all player requests
            while not queue.empty():

                currentRequest = queue.get()

                if currentRequest == "Create Player":
                    try:
                        players[index] = Player(index, trailSpriteGroup)
                        playerSpriteGroup.add(players[index])
                    except Exception as e:
                        print(f"Error when creating player {index+1}: {e}")
                        players[index] = None

                elif currentRequest == "Left":
                    if players[index].xVel == 0:
                        try:
                            players[index].turnRequests.put_nowait("Left")
                        except mp.queues.Full:
                            pass
                
                elif currentRequest == "Right":
                    if players[index].xVel == 0:
                        try:
                            players[index].turnRequests.put_nowait("Right")
                        except mp.queues.Full:
                            pass

                elif currentRequest == "Up":
                    if players[index].yVel == 0:
                        try:
                            players[index].turnRequests.put_nowait("Up")
                        except mp.queues.Full:
                            pass

                elif currentRequest == "Down":
                    if players[index].yVel == 0:
                        try:
                            players[index].turnRequests.put_nowait("Down")
                        except mp.queues.Full:
                            pass

                elif currentRequest == "Stop":
                    try:
                        players[index].die()

                    except AttributeError: # Player died before leaving, just drop exception
                        pass

            if players[index] is None:
                playerQsInUse[index].value = False
            elif players[index].fullyDead:
                playerQsInUse[index].value = False
                players[index].kill()
                players[index] = None
            else:
                playerQsInUse[index].value = True

        clock.tick(60)

        playerDataStr = ""

        screen.fill((127.5,127.5,127.5))

        for sprite in trailSpriteGroup:
            if players[sprite.playerNo] is None:
                try:
                    Player.obstacleTiles.remove((sprite.rect.x//4, sprite.rect.y//4))
                except ValueError:
                    pass
                sprite.kill()
            else:
                sprite.colour = players[sprite.playerNo].colour
                sprite.draw(screen)


        for index, sprite in enumerate(playerSpriteGroup):
            sprite.update()
            sprite.draw(screen)
            playerDataStr += sprite.getData()
            if index != len(playerSpriteGroup)-1:
                playerDataStr += ";"
        
        currentPlayerDataArray._lock.acquire()
        currentPlayerDataArray.__setslice__(0, len(playerDataStr), playerDataStr) # Set array to the data string
        currentPlayerDataArray.__setslice__(len(playerDataStr), 59, ['\x00' for x in range(59-len(playerDataStr))])
        currentPlayerDataArray._lock.release()

        pygame.display.update()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                serverProcess.stop()
                running = False

    pygame.quit()
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
