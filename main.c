#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "parse_rec/parse_rec.h"
#include "placing/placing.h"

//Using SDL, SDL_image, standard IO, math, and strings
#include <SDL2/SDL.h>
#include <stdbool.h>

//Screen dimension constants
#define SCREEN_WIDTH 640
#define SCREEN_HEIGHT 480

//Starts up SDL and creates window
bool init();

//Frees media and shuts down SDL
void shutdown();

//The window we'll be rendering to
SDL_Window* gWindow = NULL;

//The window renderer
SDL_Renderer* gRenderer = NULL;

bool init()
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

void shutdown()
{
	//Destroy window	
	SDL_DestroyRenderer( gRenderer );
	SDL_DestroyWindow( gWindow );
	gWindow = NULL;
	gRenderer = NULL;
}

int plot(struct rec *list, int length, int enclosing_width, int enclosing_height)
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

void sum_hw(struct rec *list, int length, int *height, int *width)
{
    int i;
    *height = 0;
    *width = 0;
    for(i = 0; i < length; i++){
        *height += list[i].height;
        *width += list[i].width;
    }
    return;
}

int total_area(struct rec *list, int length)
{
    int area = 0;
    int i;
    for(i = 0; i < length; i++){
        area += list[i].height*list[i].width;
    }
    return area;
}

int main(int argc, char *argv[]){
    if(argc != 2){
        fprintf(stderr, "No input file found!\n");
    }
    FILE *fp;
    if( (fp = fopen(argv[1], "r")) == NULL ){
        fprintf(stderr, "Error. File could not be opened.\n");
        return 0;
    }

    struct rec *list;
    int length;
    int i;
    int h;
    int w;

    list = rec_list_alloc(fp, &length);

    printf("reclist_alloc length %d\n", length);
    sum_hw(list, length, &h, &w);
    printf("sum h: %d, sum w: %d\n", h, w);

    Placing *p = alloc_placing(400, 400);//h, w);

    for(i = 0; i < length; i++){
        printf("id = %d, h = %d, w = %d\n", list[i].id, list[i].height, list[i].width);
        printf("Status add:%d\n", add_rec(p, list + i));
        printf("x = %d, y = %d\n", list[i].x, list[i].y);
        print_placing(p);
    }
    plot(list, length, 400, 400);

    free(list);
    fclose(fp);

    free_placing(p);

    return 0;
}
