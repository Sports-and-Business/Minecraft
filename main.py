from __future__ import division

import sys
import math
import random
import time

from collections import deque
from pyglet import image
from pyglet.gl import *
from pyglet.graphics import TextureGroup
from pyglet.window import key, mouse

TICKS_PER_SEC = 60

# Size of sectors used to ease block loading.
SECTOR_SIZE = 16

WALKING_SPEED = 5                                                         #Constant Variables that are set to determin the fly speed and walk speed of the player character
FLYING_SPEED = 15

GRAVITY = 20.0
MAX_JUMP_HEIGHT = 1.0 # About the height of a block.
# To derive the formula for calculating jump speed, first solve
#    v_t = v_0 + a * t
# for the time at which you achieve maximum height, where a is the acceleration
# due to gravity and v_t = 0. This gives:
#    t = - v_0 / a
# Use t and the desired MAX_JUMP_HEIGHT to solve for v_0 (jump speed) in
#    s = s_0 + v_0 * t + (a * t^2) / 2
JUMP_SPEED = math.sqrt(2 * GRAVITY * MAX_JUMP_HEIGHT)
TERMINAL_VELOCITY = 50

PLAYER_HEIGHT = 2                                                 #The 2 here is equivlent to the hieght of two blocks

if sys.version_info[0] >= 3:                                      #Depending on the version bing used, this will also effect the range of a player vision or field of view
    xrange = range

def cube_vertices(x, y, z, n):
    """ Return the vertices of the cube at position x, y, z with size 2*n.
     Parameters
    ----------
    x, y, z - position coordinates
	n - half of the edge length of the cube
    Returns
    -------
    cube vertices: 24-tuple of ints
	"""
    return [
        x-n,y+n,z-n, x-n,y+n,z+n, x+n,y+n,z+n, x+n,y+n,z-n,  # top    Each of these rows being calcualted represent one set of vertices on cube, which one they
        x-n,y-n,z-n, x+n,y-n,z-n, x+n,y-n,z+n, x-n,y-n,z+n,  # bottom represent can be seen with the associated label. This is important for player collision 
        x-n,y-n,z-n, x-n,y-n,z+n, x-n,y+n,z+n, x-n,y+n,z-n,  # left   and fitting the blocks togther properly. 
        x+n,y-n,z+n, x+n,y-n,z-n, x+n,y+n,z-n, x+n,y+n,z+n,  # right
        x-n,y-n,z+n, x+n,y-n,z+n, x+n,y+n,z+n, x-n,y+n,z+n,  # front
        x+n,y-n,z-n, x-n,y-n,z-n, x-n,y+n,z-n, x+n,y+n,z-n,  # back
    ]


def tex_coord(x, y, n=4):
    """ Return the bounding vertices of the texture square.
	Parameters
    ----------
    x, y - 2D position coordinates of texture file texture.png
	n = 4 - hard coded size of texture in file
    Returns
    -------
   8 integers, the bounding coordinates of each texture square
    """
    m = 1.0 / n                                               #This values is essentially hard coded to be .25 as n=4 in the function definition  
    dx = x * m                                                
    dy = y * m
    return dx, dy, dx + m, dy, dx + m, dy + m, dx, dy + m    #This return is what sends that proper coordinates each texture, as it important to change due to      
                                                             #possible difference in height for where the block can be placed, which is why it is not hard coded.

def tex_coords(top, bottom, side):
    """ Return a list of the texture squares for the top, bottom and side.
    Parameters
    ----------
    top, bottom, side - coordinates of the sides of the cube to be textured
    Returns
    -------
    result - tuple of texture mappings for the 6 sides of the block
	"""
    top = tex_coord(*top)                                 #This will call the function above and then store each value as tuple before sending 
    bottom = tex_coord(*bottom)                           #these values back as a return. 
    side = tex_coord(*side)
    result = []
    result.extend(top)
    result.extend(bottom)
    result.extend(side * 4)
    return result


TEXTURE_PATH = 'texture.png'                          #This calls the texture.png file that comes with the program which is what allows the program to 
                                                      #properly get the textures that are used in the program.
GRASS = tex_coords((1, 0), (0, 1), (0, 0))            
SAND = tex_coords((1, 1), (1, 1), (1, 1))             #Each of these hard coded variables are used to acess to the correct textures for each block
BRICK = tex_coords((2, 0), (2, 0), (2, 0))            #so no block gets the wrong texture. 
STONE = tex_coords((2, 1), (2, 1), (2, 1))

FACES = [                                             #This is set so a block in particular can check around itself in any possible direction and will                   
    ( 0, 1, 0),                                       #be very important in later functions. 
    ( 0,-1, 0),
    (-1, 0, 0),
    ( 1, 0, 0),
    ( 0, 0, 1),
    ( 0, 0,-1),
]


def normalize(position):
    """ Accepts `position` of arbitrary precision and returns the block
    containing that position.
    Parameters
    ----------
    position : tuple of len 3
    Returns
    -------
    block_position : tuple of ints of len 3
    """
    x, y, z = position
    x, y, z = (int(round(x)), int(round(y)), int(round(z)))  #This uses round to make sure the values presented are whole numbers and not decimals
    return (x, y, z)                                         # as they could be due to the nature of the game.


def sectorize(position):
    """ Returns a tuple representing the sector for the given `position`.
    Parameters
    ----------
    position : tuple of len 3
    Returns
    -------
    sector : tuple of len 3
    """
    x, y, z = normalize(position)
    x, y, z = x // SECTOR_SIZE, y // SECTOR_SIZE, z // SECTOR_SIZE  #SECTOR_SIZE was determined as a constant above, this is used to create sectors for 
    return (x, 0, z)                                                #determining the position of the player easier. 


class Model(object):

    def __init__(self):
		""" Default initializer for world model
		Creates variables for managing the state of the world
		"""
        # A Batch is a collection of vertex lists for batched rendering.
        self.batch = pyglet.graphics.Batch()

        # A TextureGroup manages an OpenGL texture.
        self.group = TextureGroup(image.load(TEXTURE_PATH).get_texture())

        # A mapping from position to the texture of the block at that position.
        # This defines all the blocks that are currently in the world.
        self.world = {}

        # Same mapping as `world` but only contains blocks that are shown.
        self.shown = {}

        # Mapping from position to a pyglet `VertextList` for all shown blocks.
        self._shown = {}

        # Mapping from sector to a list of positions inside that sector.
        self.sectors = {}

        # Simple function queue implementation. The queue is populated with
        # _show_block() and _hide_block() calls
        self.queue = deque()

        self._initialize()

    def _initialize(self):
        """ Helper initializer function, called by default initializer
		Initialize the world by creating all the blocks and giving them coordinates in the world map.
		Uses hard coded variables to initialize the size of the world, and random variables to generate terrain
        """
        HalfWorld = 80  # 1/2 width and height of world, with this being half of the created world
        step = 1  # step size, with 1 then being in relation to 1 block. 
        yHeight = 0  # initial y height, with 0 represented on the ingame coordinated system.
        for x in xrange(-HalfWorld, HalfWorld + 1, step):
            for z in xrange(-HalfWorld, HalfWorld + 1, step):
                # create a layer stone an grass everywhere. Stone is the unbreakable block which is used a base for the world
                self.add_block((x, yHeight - 2, z), GRASS, immediate=False)   #Grass is created one a layer above the unbreakable stone blocks 
                self.add_block((x, yHeight - 3, z), STONE, immediate=False)
                if x in (-HalfWorld, HalfWorld) or z in (-HalfWorld, HalfWorld):
                    # create outer walls, these outer walls are the ingame unbreakable walls that can be seen. 
                    for dy in xrange(-2, 3):
                        self.add_block((x, yHeight + dy, z), STONE, immediate=False)             #Stone cannot be broken

        # generate the hills randomly, it is important to note that hills can be generated within each other leading to overlaps
        o = HalfWorld - 10    #Hills themselves will begin to be generated a set distance away from the player    
        for _ in xrange(120):
            xHillPos = random.randint(-o, o)  # x position of the hill
            zHillPos = random.randint(-o, o)  # z position of the hill, Y position is less importat as this game primarily runs off of X and Z
            base = -1  # base of the hill starts a single block above the base grass while being one below where the player is 
            height = random.randint(1, 6)  # height of the hills
            sideLen = random.randint(4, 8)  # 2 * s is the side length of the hill
            slope = 1  # how quickly to taper off the hills, is the amound each slope is generated by as it goes from the top
            t = random.choice([GRASS, SAND, BRICK]) #The unbreakable stone is not an option
            for y in xrange(base, base + height):  #Two for loops that will be usd to generate the blocks into a hill
                for x in xrange(xHillPos - step, xHillPos + sideLen + 1): 
                    for z in xrange(base - sideLen, zHillPos + sideLen + 1):
                        if (x - xHillPos) ** 2 + (z - zHillPos) ** 2 > (sideLen + 1) ** 2: #checks to make sure each hill is generated properly
                            continue
                        if (x - 0) ** 2 + (z - 0) ** 2 < 5 ** 2:
                            continue
                        self.add_block((x, y, z), t, immediate=False)
                sideLen -= slope  # decrement side lenth so hills taper off

    def hit_test(self, position, vector, max_distance=8):
        """ Line of sight search from current position. If a block is
        intersected it is returned, along with the block previously in the line
        of sight. If no block is found, return None, None.
        Parameters
        ----------
        position : tuple of len 3
            The (x, y, z) position to check visibility from.
        vector : tuple of len 3
            The line of sight vector.
        max_distance : int
            How many blocks away to search for a hit.
        """
        m = 8               #constatn defined that is used to dertermine the players maximum distance
        x, y, z = position
        dx, dy, dz = vector
        previous = None
        for _ in xrange(max_distance * m): #Checks for any block in range, even if stone 
            key = normalize((x, y, z))
            if key != previous and key in self.world:  #If there is block in sight on the break key is called
                return key, previous
            previous = key
            x, y, z = x + dx / m, y + dy / m, z + dz / m
        return None, None                              #If there is no block when the break key is called

    def exposed(self, position):
        """ Returns False if given `position` is surrounded on all 6 sides by
        blocks, True otherwise.
		Parameters
        ----------
        position : tuple of len 3
            The (x, y, z) position to check visibility of.
        """
        x, y, z = position
        for dx, dy, dz in FACES:          #This will check the balues agianst the possible surrondings which is FACES
            if (x + dx, y + dy, z + dz) not in self.world:   #If there is nothing on 6 sides then it will return true
                return True
        return False

    def add_block(self, position, texture, immediate=True):
        """ Add a block with the given `texture` and `position` to the world.
        Parameters
        ----------
        position : tuple of len 3
            The (x, y, z) position of the block to add.
        texture : list of len 3
            The coordinates of the texture squares. Use `tex_coords()` to
            generate.
        immediate : bool
            Whether or not to draw the block immediately.
        """
        if position in self.world:
            self.remove_block(position, immediate)  
        self.world[position] = texture
        self.sectors.setdefault(sectorize(position), []).append(position)
        if immediate:                            #this is nesscary call as in the function immediate is hard codded to be true
            if self.exposed(position):           #this will check the surrounding of a block to make sure it can be placed    
                self.show_block(position)
            self.check_neighbors(position)

    def remove_block(self, position, immediate=True):
        """ Remove the block at the given `position`.
        Parameters
        ----------
        position : tuple of len 3
            The (x, y, z) position of the block to remove.
        immediate : bool
            Whether or not to immediately remove block from canvas.
        """
        del self.world[position]                 #removes the block at position 
        self.sectors[sectorize(position)].remove(position) #checks the sector of the player and the position in it
        if immediate:                      #immediate is hard coded to be true in the function definition 
            if position in self.shown:
                self.hide_block(position)        #This will then check the results of this 
            self.check_neighbors(position)

    def check_neighbors(self, position):
        """ Check all blocks surrounding `position` and ensure their visual
        state is current. This means hiding blocks that are not exposed and
        ensuring that all exposed blocks are shown. Usually used after a block
        is added or removed.
		Exposed blocks are added to the mapping of shown blocks while hidden
		blocks are kept in a separate mapping to reduce render time
		Parameters
        ----------
        position : tuple of len 3
            The (x, y, z) position to check visibility from.
        """
        x, y, z = position
        for dx, dy, dz in FACES:  #Uses Faces to check surroundings of the block
            key = (x + dx, y + dy, z + dz)
            if key not in self.world:
                continue
            if self.exposed(key):       #This is used to check and see what on the block is exposed then load the proper texture for the exposed sides
                if key not in self.shown:
                    self.show_block(key)
            else:
                if key in self.shown:
                    self.hide_block(key)

    def show_block(self, position, immediate=True):
        """ Show the block at the given `position`. This method assumes the
        block has already been added with add_block()
		Adds the block at the position to the list of visible block mappings
        Parameters
        ----------
        position : tuple of len 3
            The (x, y, z) position of the block to show.
        immediate : bool
            Whether or not to show the block immediately.
        """
        texture = self.world[position]
        self.shown[position] = texture #Gets the postition of the texture
        if immediate:
            self._show_block(position, texture) #immediate is had coded to be true in fucntion definiton, but this may be called in string which is what there is an else
        else:
            self._enqueue(self._show_block, position, texture) #This specifically adds the texturest that are nesscary to to display the block correctly in queue

    def _show_block(self, position, texture):
        """ Private implementation of the `show_block()` method.
		Helper function creating a texture map for the shown block
		and adding the block to the world mapping
        Parameters
        ----------
        position : tuple of len 3
            The (x, y, z) position of the block to show.
        texture : list of len 3
            The coordinates of the texture squares. Use `tex_coords()` to
            generate.
        """
        x, y, z = position
        vertex_data = cube_vertices(x, y, z, 0.5)
        texture_data = list(texture)
        # create vertex list
        # FIXME Maybe `add_indexed()` should be used instead
        self._shown[position] = self.batch.add(24, GL_QUADS, self.group, 
            ('v3f/static', vertex_data),
            ('t2f/static', texture_data))

    def hide_block(self, position, immediate=True):
        """ Hide the block at the given `position`. Hiding does not remove the
        block from the world. Hiding blocks minimizes rendering cost, as the 
		textures of hidden blocks will not be rendered
        Parameters
        ----------
        position : tuple of len 3
            The (x, y, z) position of the block to hide.
        immediate : bool
            Whether or not to immediately remove the block from the canvas.
        """
        self.shown.pop(position)
        if immediate:      #hardcoded in definition but if called in string it will be need to be queued
            self._hide_block(position)   #hides the texture of the block that is surrounded
        else:
            self._enqueue(self._hide_block, position) #queues the hide

    def _hide_block(self, position):
        """ Private implementation of the 'hide_block()` method.
		Helper function for hiding blocks. Removes the block from the current
		world mapping of block textures
		Parameters
        ----------
        position : tuple of len 3
            The (x, y, z) position of the block to hide.
        """
        self._shown.pop(position).delete() 

    def show_sector(self, sector):
        """ Ensure all blocks in the given sector that should be shown are
        drawn to the canvas.
		Parameters
        ----------
        sector : tuple of len 3
            The area of the horizontal plane which is being checked for shown blocks
        """
        for position in self.sectors.get(sector, []): #checks a sectors blocks if they are exposed then the textures will be set
            if position not in self.shown and self.exposed(position):
                self.show_block(position, False)

    def hide_sector(self, sector):
        """ Ensure all blocks in the given sector that should be hidden are
        removed from the canvas.
		Parameters
        ----------
        sector : tuple of len 3
            The area of the horizontal plane which is being checked for hidden blocks
        """
        for position in self.sectors.get(sector, []): #this will then check the sectors textures to be hidden if not exposed on faces
            if position in self.shown:
                self.hide_block(position, False)

    def change_sectors(self, before, after):
        """ Move from sector `before` to sector `after`. A sector is a
        contiguous x, y sub-region of world. Sectors are used to speed up
        world rendering.
		Parameters
        ----------
        before : tuple of len 3
            The area of the horizontal plane which the player is leaving
        after : tuple of len 3
			The area of the horizontal plane which the player is entering
		"""
        before_set = set()
        after_set = set()
        pad = 4
        for dx in xrange(-pad, pad + 1):        
            for dy in [0]:  # xrange(-pad, pad + 1): This cacluated below to show which sectore the player moves to or from
                for dz in xrange(-pad, pad + 1):
                    if dx ** 2 + dy ** 2 + dz ** 2 > (pad + 1) ** 2:
                        continue
                    if before:
                        x, y, z = before
                        before_set.add((x + dx, y + dy, z + dz))
                    if after:
                        x, y, z = after
                        after_set.add((x + dx, y + dy, z + dz))
        show = after_set - before_set
        hide = before_set - after_set
        for sector in show:
            self.show_sector(sector)   
        for sector in hide:
            self.hide_sector(sector)

    def _enqueue(self, func, *args):
        """ Add `func` to the internal queue.
		Parameters
        ----------
		func : model class func
			The function which is being enqueued to be called lateral
		args : list of function arguements
        """
        self.queue.append((func, args)) #appends a function call to the queue of fucntions that will be called

    def _dequeue(self):
        """ Pop the top function from the internal queue and call it.
        """
        func, args = self.queue.popleft() #after doing a commadn fucntion it will then be removed from the overall queue
        func(*args)

    def process_queue(self):
        """ Process the entire queue while taking periodic breaks. This allows
        the game loop to run smoothly. The queue contains calls to
        _show_block() and _hide_block() so this method should be called if
        add_block() or remove_block() was called with immediate=False
        """
        start = time.clock()
        while self.queue and time.clock() - start < 1.0 / TICKS_PER_SEC:  #The TICKS is used as the time it will parse through the QUEUE before taking a break 
            self._dequeue()                                                #this is hard coded as 60 above

    def process_entire_queue(self):
        """ Process the entire queue with no breaks.
        """
        while self.queue:
            self._dequeue()


class Window(pyglet.window.Window):

    def __init__(self, *args, **kwargs):
		""" Default initializer for window object
		Creates variables for managing the state of the window
		in which the game is rendered. Sets up user input management.
		"""
        super(Window, self).__init__(*args, **kwargs)

        # Whether or not the window exclusively captures the mouse.
        self.exclusive = False

        # When flying gravity has no effect and speed is increased.
        self.flying = False

        # Strafing is moving lateral to the direction you are facing,
        # e.g. moving to the left or right while continuing to face forward.
        #
        # First element is -1 when moving forward, 1 when moving back, and 0
        # otherwise. The second element is -1 when moving left, 1 when moving
        # right, and 0 otherwise.
        self.strafe = [0, 0]

        # Current (x, y, z) position in the world, specified with floats. Note
        # that, perhaps unlike in math class, the y-axis is the vertical axis.
        self.position = (0, 0, 0)

        # First element is rotation of the player in the x-z plane (ground
        # plane) measured from the z-axis down. The second is the rotation
        # angle from the ground plane up. Rotation is in degrees.
        #
        # The vertical plane rotation ranges from -90 (looking straight down) to
        # 90 (looking straight up). The horizontal rotation range is unbounded.
        self.rotation = (0, 0)

        # Which sector the player is currently in.
        self.sector = None

        # The crosshairs at the center of the screen.
        self.reticle = None

        # Velocity in the y (upward) direction.
        self.dy = 0

        # A list of blocks the player can place. Hit num keys to cycle.
        self.inventory = [BRICK, GRASS, SAND]

        # The current block the user can place. Hit num keys to cycle.
        self.block = self.inventory[0]

        # Convenience list of num keys.
        self.num_keys = [
            key._1, key._2, key._3, key._4, key._5,
            key._6, key._7, key._8, key._9, key._0]

        # Instance of the model that handles the world.
        self.model = Model()

        # The label that is displayed in the top left of the canvas.
        self.label = pyglet.text.Label('', font_name='Arial', font_size=18,
            x=10, y=self.height - 10, anchor_x='left', anchor_y='top',
            color=(0, 0, 0, 255))

        # This call schedules the `update()` method to be called
        # TICKS_PER_SEC. This is the main game event loop.
        pyglet.clock.schedule_interval(self.update, 1.0 / TICKS_PER_SEC)

    def set_exclusive_mouse(self, exclusive):
        """ If `exclusive` is True, the game will capture the mouse, if False
        the game will ignore the mouse. When captured the mouse is locked to the 
		center of the game window and affects the in game viewpoint
        """
        super(Window, self).set_exclusive_mouse(exclusive) #This is specifcally called thanks to the esc key being called
        self.exclusive = exclusive                         #locks the mouse

    def get_sight_vector(self):
        """ Returns the current line of sight vector indicating the direction
        the player is looking.
		Returns
        -------
        vector : tuple of len 3
			The angle the player is looking in x, y, and z coordinates.
        """
        x, y = self.rotation
        # y ranges from -90 to 90, or -pi/2 to pi/2, so m ranges from 0 to 1 and
        # is 1 when looking ahead parallel to the ground and 0 when looking
        # straight up or down.
        m = math.cos(math.radians(y))
        # dy ranges from -1 to 1 and is -1 when looking straight down and 1 when
        # looking straight up.
        dy = math.sin(math.radians(y))
        dx = math.cos(math.radians(x - 90)) * m
        dz = math.sin(math.radians(x - 90)) * m
        return (dx, dy, dz)

    def get_motion_vector(self):
        """ Returns the current motion vector indicating the velocity of the
        player.
        Returns
        -------
        vector : tuple of len 3
            Tuple containing the velocity in x, y, and z respectively.
        """
        if any(self.strafe):
            x, y = self.rotation
            strafe = math.degrees(math.atan2(*self.strafe))
            y_angle = math.radians(y)             #This is set thanks to the math being imported 
            x_angle = math.radians(x + strafe)    #this sets the base values for the movments
            if self.flying:
                m = math.cos(y_angle)
                dy = math.sin(y_angle)
                if self.strafe[1]:
                    # Moving left or right.
                    dy = 0.0
                    m = 1
                if self.strafe[0] > 0:
                    # Moving backwards. while keeping the camera straight is a strafe
                    dy *= -1
                # When you are flying up or down, you have less left and right
                # motion, which is important as it limits and might be seen as an error if not read
                dx = math.cos(x_angle) * m
                dz = math.sin(x_angle) * m
            else:
                dy = 0.0
                dx = math.cos(x_angle)
                dz = math.sin(x_angle)
        else:
            dy = 0.0   #if not moving in any direction than teh values should not change
            dx = 0.0
            dz = 0.0
        return (dx, dy, dz)

    def update(self, dt):
        """ This method is scheduled to be called repeatedly by the pyglet
        clock. Handles all world changes including player sector changes and 
		block changes.
        Parameters
        ----------
        dt : float, unitless time
            The change in time since the last call.
        """
        self.model.process_queue()
        sector = sectorize(self.position)     #Gets the sector so it can be updated
        if sector != self.sector:
            self.model.change_sectors(self.sector, sector) #It views the surronding sectors for use
            if self.sector is None:
                self.model.process_entire_queue() #This goes through the queue checking each sectors uses
            self.sector = sector
        m = 8
        dt = min(dt, 0.2)
        for _ in xrange(m):
            self._update(dt / m)

    def _update(self, dt):
        """ Private implementation of the `update()` method. This is where most
        of the motion logic lives, along with gravity and collision detection.
		Handles players real time position in the world.
        Parameters
        ----------
        dt : float
            The change in time since the last call.
        """
        # walking
        speed = FLYING_SPEED if self.flying else WALKING_SPEED
        d = dt * speed # distance covered this tick.
        dx, dy, dz = self.get_motion_vector()
        # New position in space, before accounting for gravity.
        dx, dy, dz = dx * d, dy * d, dz * d
        # gravity
        if not self.flying:
            # Update your vertical speed: if you are falling, speed up until you
            # hit terminal velocity; if you are jumping, slow down until you
            # start falling.
            self.dy -= dt * GRAVITY
            self.dy = max(self.dy, -TERMINAL_VELOCITY)
            dy += self.dy * dt
        # collisions
        x, y, z = self.position
        x, y, z = self.collide((x + dx, y + dy, z + dz), PLAYER_HEIGHT)
        self.position = (x, y, z)

    def collide(self, position, height):
        """ Checks to see if the player at the given `position` and `height`
        is colliding with any blocks in the world.
        Parameters
        ----------
        position : tuple of len 3
            The (x, y, z) position to check for collisions at.
        height : int or float
            The height of the player.
        Returns
        -------
        position : tuple of len 3
            The new position of the player taking into account collisions.
        """
        # How much overlap with a dimension of a surrounding block you need to
        # have to count as a collision. If 0, touching terrain at all counts as
        # a collision. If .49, you sink into the ground, as if walking through
        # tall grass. If >= .5, you'll fall through the ground.
        pad = 0.25
        pos = list(position)
        normpos = normalize(position)
        for face in FACES:  # check all surrounding blocks
            for i in xrange(3):  # check each dimension independently
                if not face[i]:
                    continue
                # How much overlap you have with this dimension.
                d = (pos[i] - normpos[i]) * face[i]
                if d < pad:
                    continue
                for dy in xrange(height):  # check each height of each block to check agianst the blocks themselves
                    op = list(normpos)
                    op[1] -= dy
                    op[i] += face[i]
                    if tuple(op) not in self.model.world:
                        continue
                    pos[i] -= (d - pad) * face[i]
                    if face == (0, -1, 0) or face == (0, 1, 0):
                        # You are colliding with the ground or ceiling, so stop
                        # falling / rising.
                        self.dy = 0
                    break
        return tuple(pos)

    def on_mouse_press(self, x, y, button, modifiers):
        """ Called when a mouse button is pressed. Uses Pyglet API for mouse mappings. 
		See pyglet docs for button and modifier mappings.
        Parameters
        ----------
        x, y : int
            The coordinates of the mouse click. Always center of the screen if
            the mouse is captured.
        button : int
            Number representing mouse button that was clicked. 1 = left button,
            4 = right button.
        modifiers : int
            Number representing any modifying keys that were pressed when the
            mouse button was clicked.
        """
        if self.exclusive:
            vector = self.get_sight_vector() #gets how ar maximum view for the player is 
            block, previous = self.model.hit_test(self.position, vector) #this will then check agiasnt which block if any it is pressed
            if (button == mouse.RIGHT) or \
                    ((button == mouse.LEFT) and (modifiers & key.MOD_CTRL)):
                # ON OSX, control + left click = right click.
                if previous:
                    self.model.add_block(previous, self.block)
            elif button == pyglet.window.mouse.LEFT and block:
                texture = self.model.world[block] #Checks the proper texture agianst the click
                if texture != STONE:   #STONE is defined as unbreakable right here
                    self.model.remove_block(block)
        else:
            self.set_exclusive_mouse(True)

    def on_mouse_motion(self, x, y, dx, dy):
        """ Called when the player moves the mouse. When the mouse is exclusive
		the players in game viewpoint is adjusted.
		Otherwise, the mouse movement leaves the game completely unaadjusted
        Parameters
        ----------
        x, y : int
            The coordinates of the mouse click. Always center of the screen if
            the mouse is captured.
        dx, dy : float
            The movement of the mouse.
        """
        if self.exclusive:
            m = 0.15
            x, y = self.rotation
            x, y = x + dx * m, y + dy * m #Calculating for how fast the players vision and viewpoint changes
            y = max(-90, min(90, y))
            self.rotation = (x, y)

    def on_key_press(self, symbol, modifiers):
        """ Called when the player presses a key. Uses Pyglet API for key mappings.
		W - Dec x speed				A - Dec z speed
		S - Inc x speed				D - Inc z speed
		Esc - Unbinds mouse from window 
		Tab - Alternate player flying state
		Num keys - All num keys are enumerated to change blocks, 1,2,3 should be only textures
		All others should be null
		See pyglet docs for key mappings.
        Parameters
        ----------
        symbol : int
            Number representing the key that was pressed.
        modifiers : int
            Number representing any modifying keys that were pressed.
        """
        if symbol == key.W:
            self.strafe[0] -= 1 #sets -1 if W for forward
        elif symbol == key.S:
            self.strafe[0] += 1 #sets +1 if S is pressed for backwards
        elif symbol == key.A:
            self.strafe[1] -= 1 #sets -1 if D is pressed for right
        elif symbol == key.D:
            self.strafe[1] += 1 #sets +1 if A is pressed for left
        elif symbol == key.SPACE:
            if self.dy == 0:  #if space is pressed used jump speed to jump
                self.dy = JUMP_SPEED
        elif symbol == key.ESCAPE:
            self.set_exclusive_mouse(False) #esc sets exclusive mouse
        elif symbol == key.TAB:
            self.flying = not self.flying #tab will set flying generated off of fly speed
        elif symbol in self.num_keys:
            index = (symbol - self.num_keys[0]) % len(self.inventory) #sets which block is placed on right click
            self.block = self.inventory[index]

    def on_key_release(self, symbol, modifiers):
        """ Called when the player releases a key. Key release only adjusts the
		players movement speed, with the release of W,A,S,D having inverse affect
		to their respective presses.
		See pyglet docs for key
        mappings.
        Parameters
        ----------
        symbol : int
            Number representing the key that was pressed.
        modifiers : int
            Number representing any modifying keys that were pressed.
        """
        if symbol == key.W:
            self.strafe[0] += 1 #on release of W +1 is set to stop moving forwards
        elif symbol == key.S:
            self.strafe[0] -= 1#on release of S -1 is set to stop moving backward
        elif symbol == key.A:
            self.strafe[1] += 1#on release of A +1 is set to stop moving left
        elif symbol == key.D:
            self.strafe[1] -= 1#on release of D -1 is set to stop moving right

    def on_resize(self, width, height):
        """ Called when the window is resized to a new `width` and `height`.
		Adjusts the coordinates of the reticle, along with the viewpoint of the player
		in the x and y plane
		Parameters
		-----------
		width: px width of new window
		height: px height of new window
        """
        # label, used to set the height constant
        self.label.y = height - 10
        # reticle, to represent where the viewpoint of the player is 
        if self.reticle:
            self.reticle.delete()
        x, y = self.width // 2, self.height // 2
        n = 10
        self.reticle = pyglet.graphics.vertex_list(4,
            ('v2i', (x - n, y, x + n, y, x, y - n, x, y + n))
        )

    def set_2d(self):
        """Helper function to configure OpenGL to draw in 2d.
		See OpenGL documentation for more.
        """
        width, height = self.get_size() #Checks wrer the view is looking and then the sets the value for 2D implementation
        glDisable(GL_DEPTH_TEST)
        glViewport(0, 0, width, height) #helps to set he view point of the player using GL
        glMatrixMode(GL_PROJECTION)  
        glLoadIdentity()
        glOrtho(0, width, 0, height, -1, 1)
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()

    def set_3d(self):
        """ Helper function to configure OpenGL to draw in 3d.
		See OpenGL documentation for more.
        """
        width, height = self.get_size()
        glEnable(GL_DEPTH_TEST)
        glViewport(0, 0, width, height) #gets the view port so it can properly generate a 3D enviroment for the player
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        gluPerspective(65.0, width / float(height), 0.1, 60.0)
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()
        x, y = self.rotation
        glRotatef(x, 0, 1, 0)
        glRotatef(-y, math.cos(math.radians(x)), 0, math.sin(math.radians(x)))
        x, y, z = self.position
        glTranslatef(-x, -y, -z)

    def on_draw(self):
        """ Called by pyglet to draw the canvas.
        """
        self.clear() #clears the entire map canvas
        self.set_3d() #sets the 3D view of the program
        glColor3d(1, 1, 1)
        self.model.batch.draw()
        self.draw_focused_block()
        self.set_2d()       #sets the 2D view for the program 
        self.draw_label()
        self.draw_reticle() #sets the players cross hair reticle on the screen 

    def draw_focused_block(self):
        """ Draw black edges around the block that is currently under the
        crosshairs.
        """
        vector = self.get_sight_vector() #gets the sight of the player
        block = self.model.hit_test(self.position, vector)[0]
        if block: #if ther is block then it will check agianst vertices of the block and draw around it to set the focus on that block
            x, y, z = block
            vertex_data = cube_vertices(x, y, z, 0.51)
            glColor3d(0, 0, 0)
            glPolygonMode(GL_FRONT_AND_BACK, GL_LINE)
            pyglet.graphics.draw(24, GL_QUADS, ('v3f/static', vertex_data))
            glPolygonMode(GL_FRONT_AND_BACK, GL_FILL)

    def draw_label(self):
        """ Draw the label in the top left of the screen.
		Label shows players current FPS, and x,y,z coordinate location.
        """
        x, y, z = self.position
        self.label.text = '%02d (%.2f, %.2f, %.2f) %d / %d' % ( #This sets the top left lables for the player so they can see coordinates and other information 
            pyglet.clock.get_fps(), x, y, z,
            len(self.model._shown), len(self.model.world))
        self.label.draw()

    def draw_reticle(self):
        """ Draw the crosshairs in the center of the screen.
        """
        glColor3d(0, 0, 0)   #Sets the color of the cross hairs from GL
        self.reticle.draw(GL_LINES)  #creates a simple reticle from Lines


def setup_fog():
    """ Helper function to configure the OpenGL fog properties.
	See OpenGL documentation for more.
    """
    # Enable fog. Fog "blends a fog color with each rasterized pixel fragment's
    # post-texturing color."
    glEnable(GL_FOG)
    # Set the fog color.
    glFogfv(GL_FOG_COLOR, (GLfloat * 4)(0.5, 0.69, 1.0, 1))
    # Say we have no preference between rendering speed and quality.
    glHint(GL_FOG_HINT, GL_DONT_CARE)
    # Specify the equation used to compute the blending factor.
    glFogi(GL_FOG_MODE, GL_LINEAR)
    # How close and far away fog starts and ends. The closer the start and end,
    # the denser the fog in the fog range.
    glFogf(GL_FOG_START, 20.0)
    glFogf(GL_FOG_END, 60.0)


def setup():
    """ Helper function to setup basic OpenGL configuration.
	See OpenGL documentation for more.
    """
    # Set the color of "clear", i.e. the sky, in rgba.
    glClearColor(0.5, 0.69, 1.0, 1)
    # Enable culling (not rendering) of back-facing facets -- facets that aren't
    # visible to you.
    glEnable(GL_CULL_FACE)
    # Set the texture minification/magnification function to GL_NEAREST (nearest
    # in Manhattan distance) to the specified texture coordinates. GL_NEAREST
    # "is generally faster than GL_LINEAR, but it can produce textured images
    # with sharper edges because the transition between texture elements is not
    # as smooth."
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
    setup_fog()


def main():
    window = Window(width=800, height=600, caption='Pyglet', resizable=True)
    # Hide the mouse cursor and prevent the mouse from leaving the window.
    window.set_exclusive_mouse(True) #this is done on the exclusive set when esc is pressed
    setup()
    pyglet.app.run()


if __name__ == '__main__':
    main()
