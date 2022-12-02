#include <iostream>
#include <chrono>
#include <thread>
#include <vector>
#include <fstream>
using std::fstream;

/**
 * get_int() - Parse an integer from a string, and exit if the parse fails.
 * @s:      String to parse.
 * @msg:    Error message to print (with a single %s specifier) on errors.
 * Return:  The integer value corresponding to @s.
 */
int get_int(const char *s, const char *msg)
{
        int value;
        value = strtol(s, NULL, 10);
        if (value == 0) {
                printf(msg, s);
                exit(1);
        }
        return value;
}

void set_idle_priority(void) {
        struct sched_param param;
        param.sched_priority = 0;
        int s = pthread_setschedparam(pthread_self(), SCHED_IDLE, &param);
        if (s != 0) printf("Pthread_setschedparam error!n");
}

void compute(int id, int n, int mode) {
    auto start = std::chrono::steady_clock::now();
    unsigned long long counter = 0;
    std::ofstream file("./temp/compute_" + std::to_string(id) + "-" + std::to_string(n) + ".log", fstream::out);
    if(mode == 1)
        set_idle_priority();
    while (1) { 
        counter += 1; 
        if (counter % 1000000ull == 0) {
            auto now = std::chrono::steady_clock::now();
            if (now - start > std::chrono::seconds(1)) {
                file << counter * 1000000000ull / std::chrono::duration_cast<std::chrono::nanoseconds>(now - start).count()
                          << " increments/s" 
                          << std::endl;
                file.flush();
                counter = 0;
                start = now;
            }
        }
    }
    file.close();
}


int main (int argc, char** argv) {
    int num_threads = get_int(argv[1], "bad thread num:%s\n");
    /* mode = 0, SCHE_IDLE; mode = 1, normal CFS */
    int mode = get_int(argv[2], "bad mode num:%s\n");
    std::vector<std::thread> workers;
    for (int  i = 0; i < num_threads; i++) {
        workers.push_back(std::thread(compute, i, num_threads, mode));
    }
    if(mode == 1)
        set_idle_priority();
    for(unsigned i = 0; i < workers.size(); i++) {
            workers[i].join();
    }
    return 0;
}


