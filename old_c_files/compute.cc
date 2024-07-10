#include <iostream>
#include <chrono>

int main (void) {
    unsigned long long counter = 0;
    auto start = std::chrono::steady_clock::now();

    while (1) { 
        counter += 1; 
        if (counter % 100000000ull == 0) {
            auto now = std::chrono::steady_clock::now();
            if (now - start > std::chrono::seconds(1)) {
                std::cout << counter * 1000000000ull / std::chrono::duration_cast<std::chrono::nanoseconds>(now - start).count()
                          << " increments/s" 
                          << std::endl;
                counter = 0;
                start = now;
            }
        }
    }
    return 0;
}
