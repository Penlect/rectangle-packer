//Using SDL, SDL_image, standard IO, math, and strings
#include <SDL2/SDL.h>
#include <stdbool.h>

#include "../rectangle_packer.h"

//Screen dimension constants
#define SCREEN_WIDTH 1240
#define SCREEN_HEIGHT 880

//The window we'll be rendering to
SDL_Window* gWindow = NULL;

//The window renderer
SDL_Renderer* gRenderer = NULL;

static bool init()
{
	//Initialization flag
	bool success = true;

	//Initialize SDL
	if( SDL_Init( SDL_INIT_VIDEO ) < 0 ){
		printf( "SDL could not initialize! SDL Error: %s\n", SDL_GetError() );
		success = false;
	}
	else{
		//Create window
		gWindow = SDL_CreateWindow( "SDL Tutorial", SDL_WINDOWPOS_UNDEFINED, SDL_WINDOWPOS_UNDEFINED, SCREEN_WIDTH, SCREEN_HEIGHT, SDL_WINDOW_SHOWN );
		if( gWindow == NULL ){
			printf( "Window could not be created! SDL Error: %s\n", SDL_GetError() );
			success = false;
		}
		else{
			//Create renderer for window
			gRenderer = SDL_CreateRenderer( gWindow, -1, SDL_RENDERER_ACCELERATED );
			if( gRenderer == NULL ){
				printf( "Renderer could not be created! SDL Error: %s\n", SDL_GetError() );
				success = false;
			}
			else{
				//Initialize renderer color
				SDL_SetRenderDrawColor( gRenderer, 0xFF, 0xFF, 0xFF, 0xFF );
			}
		}
	}

	return success;
}

static void shutdown()
{
	//Destroy window	
	SDL_DestroyRenderer( gRenderer );
	SDL_DestroyWindow( gWindow );
	gWindow = NULL;
	gRenderer = NULL;
}

int plot(Rectangle *list, int length, int enclosing_width, int enclosing_height)
{
    int i;

	//Start up SDL and create window
	if( !init() ){
		printf( "Failed to initialize!\n" );
	}
	else{
        //Main loop flag
        bool quit = false;

        //Event handler
        SDL_Event e;

        //While application is running
        while( !quit ){
            //Handle events on queue
            while( SDL_PollEvent( &e ) != 0 ){
                //User requests quit
                if( e.type == SDL_QUIT ){
                    quit = true;
                }
            }

            //Clear screen
            SDL_SetRenderDrawColor( gRenderer, 0x00, 0x00, 0x00, 0x00 );
            SDL_RenderClear( gRenderer );

            SDL_SetRenderDrawColor( gRenderer, 0xFF, 0xFF, 0xFF, 0xFF );
            SDL_Rect enclosing = {0, 0, enclosing_width, enclosing_height};
            SDL_RenderFillRect( gRenderer, &enclosing );

            for(i = 0; i < length; i++){

                //Render red filled quad
                SDL_Rect fillRect = {list[i].x, list[i].y, list[i].width, list[i].height};
                SDL_SetRenderDrawColor( gRenderer, i*40%0xFF, (i*12 + i*i*5)%0xFF + 0x40, i*i%0xFF, 0x00 );		
                SDL_RenderFillRect( gRenderer, &fillRect );
                
                //Draw blue horizontal line
                //SDL_SetRenderDrawColor( gRenderer, i*40%0xFF, (i*12 + i*i*5)%0xFF, i*i%0xFF, 0x00 );		
                SDL_RenderDrawLine( gRenderer, 0, list[i].y + list[i].height, SCREEN_WIDTH, list[i].y + list[i].height );
                SDL_RenderDrawLine( gRenderer, list[i].x + list[i].width, 0, list[i].x + list[i].width, SCREEN_HEIGHT );

                //Update screen

            }


            SDL_RenderPresent( gRenderer );

		}
	}

	//Free resources and shutdown SDL
	shutdown();

	return 0;
}
