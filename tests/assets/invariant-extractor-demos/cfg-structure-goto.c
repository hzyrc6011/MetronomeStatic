#include <stdio.h>

int calc(int a)
{
    return a + 1;
}

int close_data(int channel)
{
    return 0;
}

int goto_structure(int a)
{

    a += 2;
    a += 3;
A:
    if (a < 10)
    {
        a = a + 2;
        a += 5;
    }
    if (a < 100)
    {
        a -= 1;
        goto A;
    }
    a += 10;
    return a;
}

int main()
{
    printf("%d\n", goto_structure(0));
    return 0;
}