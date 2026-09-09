/* Copyright (c) 2019, Stanford University
 *
 * Permission to use, copy, modify, and/or distribute this software for any
 * purpose with or without fee is hereby granted, provided that the above
 * copyright notice and this permission notice appear in all copies.
 *
 * THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
 * WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
 * MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
 * ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
 * WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
 * ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
 * OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.
 */

// This file contains a collection of tests for the Linux implementation
// of Homa
//
// Usage:
// homaTest host:port [options] op op ...
//
// host:port gives the location of a server to invoke
// Each op specifies a particular test to perform
#include <atomic>
#include <cassert>
#include <ctime>
#include<chrono>
#include <errno.h>
#include <iostream>
#include <fstream>
#include <netinet/if_ether.h>
#include <netinet/ip.h>
#include <netinet/udp.h>
#include <netdb.h>
#include <netinet/tcp.h>
#include <poll.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <unistd.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <sys/syscall.h>
#include <arpa/inet.h>
#include <sys/ioctl.h>
#include <sys/types.h>
#include <sys/resource.h>
#include <inttypes.h>
#include <vector>
#include <queue>
#include <thread>
#include <mutex>          // std::mutex
#include <condition_variable> // std::condition_variable
#include <sched.h>
#include <sstream>
//#include "../uapi_linux_nd.h"
#include "test_utils.h"
#ifndef ETH_MAX_MTU
#define ETH_MAX_MTU	0xFFFFU
#endif

#ifndef UDP_SEGMENT
#define UDP_SEGMENT		103
#endif

#define CLIENT_PRINT_CSW_COUNT
#define CLIENT_PRINT_VRUNTIME

/* Determines message size in bytes for tests. */
int length = 1000000;

/* How many iterations to perform for the test. */
int thread_count = 100;
std::atomic<int> connected_count;
/* Used to generate "somewhat random but predictable" contents for buffers. */
int seed = 12345;

// std::queue<uint64_t> time_q;
std::mutex mtx;           // mutex for critical section
std::condition_variable cv;
int limit = 1024;
// bool queue_available() {return time_q.size() < (long unsigned int)limit;}
volatile int stop_count;

/* maximum latency will be 100ms */
#define MAX_HIST_VALUE 100000 
/* Count in us-scale */
#define NUM_BINS 100000 

std::vector<std::atomic<long long>> time_hist(MAX_HIST_VALUE);


void local_add_to_timehist(std::vector<long long> &local_time_hist, double latency) {
	// printf("latency: %f\n", latency);
	if(latency > MAX_HIST_VALUE)
		latency = MAX_HIST_VALUE - 1;
	local_time_hist[int(latency)] += 1; 
}

double local_get_mean_timehist(std::vector<long long> &local_time_hist) {
    double mean = 0.0;
	double count = 0;
    for (int i = 0; i < NUM_BINS; i++) {
        mean += static_cast<double>(local_time_hist[i]) * i;
		count += static_cast<double>(local_time_hist[i]);
    }
    mean /= count;
	return mean;
}

// Function to estimate the percentile from the histogram
double local_estimate_percentile(std::vector<long long> &local_time_hist, double percentile) {
    double total = 0;
	double target_value = 0;
    for (int i = 0; i < NUM_BINS; i++) {
        total += local_time_hist[i];
    }
	target_value = percentile * total;
	total = 0;
    for (int i = 0; i < NUM_BINS; i++) {
        total += local_time_hist[i];
        if (total >= target_value) {
            return i;
        }
    }
    return -1; // Percentile estimation failed
}

void add_to_timehist(std::vector<std::atomic<long long>> &local_time_hist, double latency) {
	// printf("latency: %f\n", latency);
	if(latency > MAX_HIST_VALUE)
		latency = MAX_HIST_VALUE;
	local_time_hist[int(latency * NUM_BINS / MAX_HIST_VALUE)].fetch_add(1, std::memory_order_relaxed); 
}

double get_mean_timehist(std::vector<std::atomic<long long>> &local_time_hist) {
    double mean = 0.0;
	double count = 0;
    for (int i = 0; i < NUM_BINS; i++) {
        mean += static_cast<double>(local_time_hist[i].load()) * i;
		count += static_cast<double>(local_time_hist[i].load());
    }
    mean /= count;
	return mean;
}

// Function to estimate the percentile from the histogram
double estimate_percentile(std::vector<std::atomic<long long>> &local_time_hist, double percentile) {
    double total = 0;
	double target_value = 0;
    for (int i = 0; i < NUM_BINS; i++) {
        total += local_time_hist[i].load();
    }
	target_value = percentile * total;
	total = 0;
    for (int i = 0; i < NUM_BINS; i++) {
        total += local_time_hist[i].load();
        if (total >= target_value) {
            return i;
        }
    }
    return -1; // Percentile estimation failed
}


// Function to calculate the time difference in microseconds between two timespec structures
long long diff_us(const timespec& start, const timespec& end) {
    long long diffSecs = end.tv_sec - start.tv_sec;
    long long diffNanos = end.tv_nsec - start.tv_nsec;

    // Adjust for negative nanosecond difference
    if (diffNanos < 0) {
        diffSecs--;
        diffNanos += 1000000000; // 1 billion nanoseconds in a second
    }

    // Convert the difference to microseconds
    long long diffMicros = diffSecs * 1000000LL + diffNanos / 1000LL;

    return diffMicros;
}

/**
 * close_fd() - Helper method for "close" test: sleeps a while, then closes
 * an fd
 * @fd:   Open file descriptor to close.
 */
void close_fd(int fd)
{
	// sleep(1);
	if (close(fd) >= 0) {
		printf("Closed fd %d\n", fd);
	} else {
		printf("Close failed on fd %d: %s\n", fd, strerror(errno));
	}
}

/**
 * print_help() - Print out usage information for this program.
 * @name:   Name of the program (argv[0])
 */
void print_help(const char *name)
{
        printf("Usage: %s host:port [options] op op ...\n\n"
                "host:port describes a server to communicate with, and each op\n"
                "selects a particular test to run (see the code for available\n"
                "tests). The following options are supported:\n\n"
                "--count      Number of times to repeat a test (default: 1000)\n"
                "--length     Size of messages, in bytes (default: 100)\n"
                "--sp       src port of connection \n"
                "--seed       Used to compute message contents (default: 12345)\n",
                name);
}


double diff_timespec(const struct timespec *time1, const struct timespec *time0) {
  return (time1->tv_sec - time0->tv_sec)
      + (time1->tv_nsec - time0->tv_nsec) / 1000000000.0;
}

void test_ndping_send(struct sockaddr *dest, int id, int io_depth, int flow_size, int src_port)
{
	// std::unique_lock<std::mutex> lck(mtx);
	// atomic_fetch_add(&connected_count, 1);
	// if(atomic_load(&connected_count) == thread_count) {
	// 	lck.unlock();
	// 	cv.notify_all();
	// }
	// else {
	// 	cv.wait(lck, []{ return atomic_load(&connected_count) == thread_count; });
	// 	lck.unlock();
	// }
	std::queue<struct timespec> time_q;
	char buffer[9000];
	int fd, i = 0;
	unsigned int cpu, node;
	// uint64_t flow_size = 10000000000000;
	// int times = 100;
	int flag = 0;
	// unsigned int size = 0;
	// std::vector<double> latency;
	uint64_t write_len = 0;
	struct timespec start_time, end_time, begin_time;
	uint64_t sent_bytes = 0;
	// uint64_t max_size = 10000000;

	std::ofstream lfile, tfile, hfile;
	pid_t pid = syscall(__NR_gettid);
	struct sockaddr_in client;
	socklen_t clientsz = sizeof(client);
	int total = 0;
	int burst = io_depth;
	bool is_first = false;
	struct timespec first_time;
	client.sin_family = AF_INET;
	client.sin_port = htons(src_port);
	client.sin_addr.s_addr = INADDR_ANY;
	std::vector<long long> local_time_hist(MAX_HIST_VALUE);

//  	struct sched_param param;
// 	param.sched_priority = 99;
//	sched_setscheduler(pid, SCHED_RR, &param);
	//int q_depth = 64, count = 0;
	    // for (int i = 0; i < count * 100; i++) {
		/* init burst io_depth packet */

	fd = socket(AF_INET, SOCK_STREAM, 0);
	if (bind(fd, reinterpret_cast<sockaddr *>(&client), sizeof(client))
			== -1) {
		printf("Couldn't bind to port %d: %s\n", src_port, strerror(errno));
		fprintf(stderr, "cannot bind\n");

		exit(1);
	}
	if (connect(fd, dest, sizeof(struct sockaddr_in)) == -1) {
		printf("Couldn't connect to dest %s\n", strerror(errno));
		fprintf(stderr, "cannot bind\n");

		exit(1);
	}

#ifdef CLIENT_PRINT_VRUNTIME
	// per-thread final virtual runtime
	std::ostringstream thread_sched_path;
	thread_sched_path << "/proc/" << pid << "/sched";
	std::ifstream sched_file(thread_sched_path.str());
	if (!sched_file.is_open()) {
		printf("Failed to open %s\n", thread_sched_path.str().c_str());
	} else {
		std::string line;
		while (std::getline(sched_file, line)) {
			if (line.find("se.vruntime") != std::string::npos) {
				// format: "se.vruntime                                  :             0.000000"
				std::istringstream iss(line);
				std::string key, colon;
				double vruntime_float;
				long long vruntime;
				if (iss >> key >> colon >> vruntime_float) {
					vruntime = static_cast<long long>(vruntime_float * 1000000); // convert to microseconds
					printf("pid: %d start-vruntime: %lld\n", pid, vruntime);
				} else {
					printf("Failed to parse vruntime line: %s\n", line.c_str());
				}
				break;
			}
		}
		sched_file.close();
	}
	fflush(stdout);
#endif

	flag = 1;
	// setsockopt(fd, IPPROTO_TCP, TCP_NODELAY, &flag, sizeof(int));
	flag = 0;
	getsockname(fd, (struct sockaddr *) &client, &clientsz);
	getcpu(&cpu, &node);
	clock_gettime(CLOCK_REALTIME, &begin_time);
	while(burst > 0) {
		total = 0;
		clock_gettime(CLOCK_REALTIME, &start_time);
		time_q.push(start_time);
		while(total < flow_size) {
			// if (burst == 1)
			// 	flag = MSG_EOR;
			// else
			// 	flag = MSG_MORE;

			if(is_first == false) {
				clock_gettime(CLOCK_MONOTONIC, &first_time);
				printf("%lld.%.9ld cpu: %d pid: %d client port: %d\n", (long long)first_time.tv_sec, first_time.tv_nsec, cpu, pid, ntohs(client.sin_port));
				is_first = true;
			}
			int result = send(fd, buffer + total, flow_size - total, flag);
			if( result < 0 ) {
				if(errno == EMSGSIZE) {
					printf("Socket write failed: %s %d\n", strerror(errno), result);
					break;
				}
			} else {
				write_len += result;
				total += result;
				sent_bytes += result;	

			}
		}
		burst--;
	}
	while(1) {
		/* receive one response */
		total = 0;
		while(total < flow_size) {
			int result = read(fd, buffer + total, flow_size - total);	
			if( result < 0 ) {
				if(errno == EMSGSIZE) {
					printf("Socket write failed: %s %d\n", strerror(errno), result);
					break;
				}
			} else {
				total += result;
			}
			if(total == flow_size) {
				start_time = time_q.front();
				clock_gettime(CLOCK_REALTIME, &end_time);
				// add_to_timehist(time_hist, diff_us(start_time, end_time));
				local_add_to_timehist(local_time_hist, diff_us(start_time, end_time));
				// latency.push_back(to_seconds(end - start));
				time_q.pop();
			}
		}
		/* send out one request */
		total = 0;
		clock_gettime(CLOCK_REALTIME, &start_time);
		time_q.push(start_time);
		total = 0;
		while(total < flow_size) {
			int result = send(fd, buffer + total, flow_size - total, flag);
			if( result < 0 ) {
				if(errno == EMSGSIZE) {
					printf("Socket write failed: %s %d\n", strerror(errno), result);
					break;
				}
			} else {
				write_len += result;
				total += result;
				sent_bytes += result;	
			}
		}
		// time_q.push(end);
		if(stop_count == 1)
			break;
	
	}
#ifdef CLIENT_PRINT_CSW_COUNT
	// per-thread involuntary context switch count
	struct rusage usage;
	getrusage(RUSAGE_THREAD, &usage);
	printf("pid: %d involuntary-context-switch-count: %ld\n", pid, usage.ru_nivcsw);
	printf("pid: %d voluntary-context-switch-count: %ld\n", pid, usage.ru_nvcsw);
#endif

#ifdef CLIENT_PRINT_VRUNTIME
    // per-thread final virtual runtime + sum_exec_runtime
    sched_file.open(thread_sched_path.str());
    if (!sched_file.is_open()) {
        std::cerr << "Failed to open " << thread_sched_path.str() << std::endl;
    } else {
        std::string line;

        bool got_vruntime = false;
        bool got_sumexec  = false;

        long long vruntime_us = -1;
        long long sumexec_us  = -1;

        while (std::getline(sched_file, line)) {
            // /proc/<pid>/sched lines typically look like:
            // "se.vruntime                                  :             0.000000"
            // "se.sum_exec_runtime                          :             1.234567"

            if (!got_vruntime && line.find("se.vruntime") != std::string::npos) {
                std::istringstream iss(line);
                std::string key, colon;
                double v_sec;
                if (iss >> key >> colon >> v_sec) {
                    vruntime_us = (long long)(v_sec * 1000000.0);
                    got_vruntime = true;
                } else {
                    printf("Failed to parse vruntime line: %s\n", line.c_str());
                }
            }

            if (!got_sumexec && line.find("se.sum_exec_runtime") != std::string::npos) {
                std::istringstream iss(line);
                std::string key, colon;
                double s_sec;
                if (iss >> key >> colon >> s_sec) {
                    sumexec_us = (long long)(s_sec * 1000000.0);
                    got_sumexec = true;
                } else {
                    printf("Failed to parse sum_exec_runtime line: %s\n", line.c_str());
                }
            }

            if (got_vruntime && got_sumexec) break;
        }

        printf("pid: %d final-vruntime(us): %lld  sum_exec_runtime(us): %lld\n",
               pid, vruntime_us, sumexec_us);

        sched_file.close();
    }
    fflush(stdout);
#endif


	lfile.open("temp/netperf-" + std::to_string(id)+".log");
	tfile.open("temp/netperf-" + std::to_string(id)+"_thpt.log");
	// tfile <<   pid << " " << ntohs(client.sin_port) << " "
	// 	<< sent_bytes  / (diff_us(begin_time, end_time) / 1000000.0) / flow_size  << std::endl;
	tfile <<   pid << " " << ntohs(client.sin_port) << " " 
	<< local_get_mean_timehist(local_time_hist) << " " << local_estimate_percentile(local_time_hist, 0.99) << " " << local_estimate_percentile(local_time_hist, 0.999) << " "
		<< sent_bytes  / (diff_us(begin_time, end_time) / 1000000.0) / flow_size  << std::endl;
	// max_size = (latency.size() > max_size) ? max_size : latency.size();
	// for(uint32_t i = 0; i < max_size; i++) {
	// 	lfile << "finish time: " << latency[i] << "\n"; 
	// 	// std::cout << "finish time: " << latency[i] << "\n"; 
	// }
	for(i = 0; i < NUM_BINS; i++) {
		std::atomic_fetch_add(&time_hist[i], local_time_hist[i]);
	}
	
	hfile.open("temp/netperf-" + std::to_string(id)+"_hist.bin", std::ios::binary);
	hfile.write(reinterpret_cast<const char*>(local_time_hist.data()), local_time_hist.size() * sizeof(long long));

	lfile.close();
	tfile.close();
	hfile.close();
	close(fd);
}

// void test_ndping_recv(int fd, struct sockaddr *dest, int id)
// {
// 	//struct sockaddr_in* in = (struct sockaddr_in*) dest;
// 	uint32_t buffer_size = 1000000;
// 	char *buffer = (char*)malloc(1000000);
// 	std::vector<double> latency;
// 	std::ofstream file;
// 	file.open("result_tcp_pingpongasync_" + std::to_string(id));
// 	int times = 70;
// 	uint64_t write_len = 0;
// 	uint64_t start_time = rdtsc();
// 	uint64_t remain = 0;
// 	while(1) {
// 		int result = read(fd, buffer, buffer_size);
// 		if( result < 0 ) {
// 			if(errno == EMSGSIZE) {
// 				break;
// 			}
// 		} else {
// 			write_len += result;
// 			remain += result;
// 		}
// 		while(remain >= 1024) {
// 			std::unique_lock<std::mutex> lck(mtx);
// 			uint64_t end = rdtsc();
// 			uint64_t start = time_q.front();
// 			if(time_q.empty())
// 				assert(false);	
// 			latency.push_back(to_seconds(end - start));
// 			time_q.pop();
// 			remain -= 1024;
// 			cv.notify_one();
// 		}
// 		uint64_t end = rdtsc();
// 		if(to_seconds(end-start_time) > times)
// 			break;
// 	}
// 	printf("finish\n");
// 	for(uint32_t i = 0; i < latency.size(); i++) {
// 		file << "finish time: " << latency[i] << "\n"; 
// 		// std::cout << "finish time: " << latency[i] << "\n"; 
// 	}
// 	file.close();

// }
/**
 * tcp_pingping() - Handles messages arriving on a given socket.
 * @fd:           File descriptor for the socket over which messages
 *                will arrive.
 * @client_addr:  Information about the client (for messages).
 */
void test_tcppingpong(int fd, struct sockaddr *dest, int id)
{
	// int flag = 1;
	// int times = 90;
	char buffer[5000];
	std::ofstream file;
	file.open("result_tcp_pingpong_"+ std::to_string(id));
	// int cur_length = 0;
	// bool streaming = false;
	uint64_t count = 0;
	// uint64_t total_length = 0;
	// uint64_t start_time;
	std::vector<double> latency;
	printf("reach here1\n");
	if (connect(fd, dest, sizeof(struct sockaddr_in)) == -1) {
		printf("Couldn't connect to dest %s\n", strerror(errno));
		exit(1);
	}
	// start_time = rdtsc();
	while (1) {
		int copied = 0;
		int rpc_length = 4096;
		// times--;
		// if(times == 0)
		// 	break;
		uint64_t start = rdtsc(), end;
		while(1) {
			int result = write(fd, buffer + copied,
				rpc_length);
			if (result <= 0) {
				printf("goto close\n");
					goto close;
			}
			rpc_length -= result;
			copied += result;
			if(rpc_length == 0)
				break;
			// return;
		}
		copied = 0;
		rpc_length = 4096;
		while(1) {
			int result = read(fd, buffer + copied,
				rpc_length);
			if (result <= 0) {
					printf("goto close2\n");
					goto close;
			}
			// printf("result:%d\n",result);
			// printf("receive rpc times:%d \n", times);
			rpc_length -= result;
			copied += result;
			if(rpc_length == 0)
				break;
			// return;
		}
		end = rdtsc();
		latency.push_back(to_seconds(end-start));
		// printf("finsh time: %f cycles:%lu\n",  to_seconds(end-start), end-start);
		if(stop_count == 1)
			break;
	//	if (total_length <= 8000000)
	//	 	printf("buffer:%s\n", buffer);
		count++;

	}
		// printf( "total len:%" PRIu64 "\n", total_length);
		// printf("done!");
close:
	sleep(10);

	for(uint32_t i = 0; i < latency.size(); i++) {
		file << "finish time: " << latency[i] << "\n"; 
		// std::cout << "finish time: " << latency[i] << "\n"; 
	}
	file.close();
	close(fd);
	return;
}

/**
 * nd_pingping() - Handles messages arriving on a given socket.
 * @fd:           File descriptor for the socket over which messages
 *                will arrive.
 * @client_addr:  Information about the client (for messages).
 */
void test_ndpingpong(int fd, struct sockaddr *dest, int id)
{
	// int flag = 1;
	int times = 90;
	// int cur_length = 0;
	// bool streaming = false;
	uint64_t count = 0;
	// uint64_t total_length = 0;
	char buffer[5000];
	std::ofstream file;
	file.open("result_nd_pingpong_"+ std::to_string(id));
	uint64_t start_time;
	std::vector<double> latency;
	printf("reach here1\n");
	if (connect(fd, dest, sizeof(struct sockaddr_in)) == -1) {
		printf("Couldn't connect to dest %s\n", strerror(errno));
		exit(1);
	}
	start_time = rdtsc();
	while (1) {
		int copied = 0;
		int rpc_length = 4096;
		// times--;
		// if(times == 0)
		// 	break;
		uint64_t start = rdtsc(), end;
		while(1) {
			int result = write(fd, buffer + copied,
				rpc_length);
			if (result <= 0) {
				printf("goto close\n");
					goto close;
			}
			rpc_length -= result;
			copied += result;
			if(rpc_length == 0)
				break;
			// return;
		}
		copied = 0;
		rpc_length = 4096;
		while(1) {
			int result = read(fd, buffer + copied,
				rpc_length);
			if (result <= 0) {
					printf("goto close2\n");
					goto close;
			}
			// printf("result:%d\n",result);
			// printf("receive rpc times:%d \n", times);
			rpc_length -= result;
			copied += result;
			if(rpc_length == 0)
				break;
			// return;
		}
		end = rdtsc();
		latency.push_back(to_seconds(end-start));
		// printf("finsh time: %f cycles:%lu\n",  to_seconds(end-start), end-start);
		if(to_seconds(end-start_time) > times)
			break;
	//	if (total_length <= 8000000)
	//	 	printf("buffer:%s\n", buffer);
		count++;

	}
		// printf( "total len:%" PRIu64 "\n", total_length);
		// printf("done!");
close:
	sleep(10);
	for(uint32_t i = 0; i < latency.size(); i++) {
		file << "finish time: " << latency[i] << "\n"; 
		// std::cout << "finish time: " << latency[i] << "\n"; 
	}
	file.close();
	close(fd);
	return;
}


int main(int argc, char** argv)
{
	int port, nextArg, tempArg, optval;
	unsigned optlen;
	// struct sockaddr_in addr_in;
	struct addrinfo *matching_addresses;
	struct sockaddr *dest;
	struct addrinfo hints;
	std::ofstream lfile, hfile;
	char *host, *port_name;
 	std::vector<std::thread> workers;
	int cpu_list[32] = {32, 96, 33, 97, 34, 98, 35, 99, 36, 100, 37, 101, 38, 102, 39, 103, 40, 104, 41, 105, 42, 106, 43, 107, 44, 108, 45, 109, 46, 110, 47, 111};
	// int cpu_list[16] = {0, 32, 4, 36, 8, 40, 12, 44, 16, 48, 20, 52, 24, 56, 28, 60};
//	int cpu_list[8] = {0, 4, 8, 12, 16, 20, 24, 28};
	// char buffer[8000000] = "abcdefgh\n";
	char *buffer = (char*)malloc(10000000);
	int pin = 0;
	int flow_size = 64;
	// buffer[63999] = 'H';
	int status;
	int fd;
	int i;
	int threads_per_core;
	int srcPort = 10000;
	int io_depth = 1;
	int inbalanced_io_depth = 16;
	int sc = 1;
	int experiment_time = 300;
	stop_count = 0;
	atomic_store(&connected_count, 0);
	lfile.open("temp/latency.log");
	hfile.open("temp/overall_hist.bin",  std::ios::binary);
    for (i = 0; i < MAX_HIST_VALUE; ++i) {
        time_hist[i].store(0);
    }
	if ((argc >= 2) && (strcmp(argv[1], "--help") == 0)) {
		print_help(argv[0]);
		exit(0);
	}
	for (i = 0; i < 8000000; i++)
		buffer[i] = (rand()) % 26 + 'a';
//	printf("buffer:%s\n", buffer);
	if (argc < 3) {
		printf("Usage: %s host:port [options] op op ...\n", argv[0]);
		exit(1);
	}
	host = argv[1];
	port_name = strchr(argv[1], ':');
	if (port_name == NULL) {
		printf("Bad server spec %s: must be 'host:port'\n", argv[1]);
		exit(1);
	}
	*port_name = 0;
	port_name++;
	port = get_int(port_name,
			"Bad port number %s; must be positive integer\n");
	for (nextArg = 2; (nextArg < argc) && (*argv[nextArg] == '-');
			nextArg += 1) {
		if (strcmp(argv[nextArg], "--help") == 0) {
			print_help(argv[0]);
			exit(0);
		} else if (strcmp(argv[nextArg], "--pin") == 0) {
			if (nextArg == (argc-1)) {
				printf("No value provided for %s option\n",
					argv[nextArg]);
				exit(1);
			}
			nextArg++;
			pin = get_int(argv[nextArg],
					"Bad pin %s; must be positive integer\n");
		} else if (strcmp(argv[nextArg], "--count") == 0) {
			if (nextArg == (argc-1)) {
				printf("No value provided for %s option\n",
					argv[nextArg]);
				exit(1);
			}
			nextArg++;
			thread_count = get_int(argv[nextArg],
					"Bad count %s; must be positive integer\n");
		} else if (strcmp(argv[nextArg], "--length") == 0) {
			if (nextArg == (argc-1)) {
				printf("No value provided for %s option\n",
					argv[nextArg]);
				exit(1);
			}
			nextArg++;
			length = get_int(argv[nextArg],
				"Bad message length %s; must be positive "
				"integer\n");
			if (length > 1000000) {
				length = 1000000;
				printf("Reducing message length to %d\n", length);
			}
		} else if (strcmp(argv[nextArg], "--sc") == 0) {
			if (nextArg == (argc-1)) {
				printf("No value provided for %s option\n",
					argv[nextArg]);
				exit(1);
			}
			nextArg++;
			sc = get_int(argv[nextArg],
				"Bad single core %s; must be positive "
				"integer\n");
		} else if (strcmp(argv[nextArg], "--sp") == 0) {
			if (nextArg == (argc-1)) {
				printf("No value provided for %s option\n",
					argv[nextArg]);
				exit(1);
			}
			nextArg++;
			srcPort = get_int(argv[nextArg],
				"Bad srcPort %s; must be positive integer\n");
		} else if (strcmp(argv[nextArg], "--limit") == 0) {
			if (nextArg == (argc-1)) {
				printf("No value provided for %s option\n",
					argv[nextArg]);
				exit(1);
			}
			nextArg++;
			limit = get_int(argv[nextArg],
				"Bad limit %s; must be positive integer\n");
		} else if (strcmp(argv[nextArg], "--iodepth") == 0) {
			if (nextArg == (argc-1)) {
				printf("No value provided for %s option\n",
					argv[nextArg]);
				exit(1);
			}
			nextArg++;
			io_depth = get_int(argv[nextArg],
				"Bad io_depth %s; must be positive integer\n");
		} else if (strcmp(argv[nextArg], "--inbalancediodepth") == 0){
			if (nextArg == (argc-1)) {
				printf("No value provided for %s option\n",
					argv[nextArg]);
				exit(1);
			}
			nextArg++;
			inbalanced_io_depth = get_int(argv[nextArg],
				"Bad inbalanced io_depth %s; must be positive integer\n");
		} else if (strcmp(argv[nextArg], "--flowsize") == 0){
			if (nextArg == (argc-1)) {
				printf("No value provided for %s option\n",
					argv[nextArg]);
				exit(1);
			}
			nextArg++;
			flow_size = get_int(argv[nextArg],
				"Bad flow size %s; must be positive integer\n");
			std::cout << "flow size:" << flow_size << std::endl;
		} else if (strcmp(argv[nextArg], "--time") == 0){
			if (nextArg == (argc-1)) {
				printf("No value provided for %s option\n",
					argv[nextArg]);
				exit(1);
			}
			nextArg++;
			experiment_time = get_int(argv[nextArg],
				"Bad experiment time %s; must be positive integer\n");
		} else {
			printf("Unknown option %s; type '%s --help' for help\n",
				argv[nextArg], argv[0]);
			exit(1);
		}
	}
	// get destination address
	memset(&hints, 0, sizeof(struct addrinfo));
	hints.ai_family = AF_INET;
	hints.ai_socktype = SOCK_DGRAM;
	status = getaddrinfo(host, "80", &hints, &matching_addresses);
	if (status != 0) {
		printf("Couldn't look up address for %s: %s\n",
				host, gai_strerror(status));
		exit(1);
	}
	dest = matching_addresses->ai_addr;
	((struct sockaddr_in *) dest)->sin_port = htons(port);
	// int *ibuf = reinterpret_cast<int *>(buffer);
	// ibuf[0] = ibuf[1] = length;
	// seed_buffer(&ibuf[2], sizeof32(buffer) - 2*sizeof32(int), seed);
	tempArg = nextArg;
	/* assume having hyperthreading */
	sc = 2 * sc;
	threads_per_core = thread_count / sc; // if sc = 1, sc = 2, threads_per_core = 26
	for(i = 0; i < thread_count; i++) {
		nextArg = tempArg;
		// memset(&addr_in, 0, sizeof(addr_in));
		// addr_in.sin_family = AF_INET;
		// addr_in.sin_port = htons(srcPort + i);
		// addr_in.sin_addr.s_addr = inet_addr("192.168.10.125");


		// if (bind(fd, (struct sockaddr *) &addr_in, sizeof(addr_in)) != 0) {
		// 	printf("Couldn't bind socket to ND port %d: %s\n", port,
		// 			strerror(errno));
		// 	return -1;
		// }

		for ( ; nextArg < argc; nextArg++) {
			if (strcmp(argv[nextArg], "tcpppasync") == 0) {
				if (i % threads_per_core == 0) {
					// the first thread on each core has an inbalanced io_depth
					workers.push_back(std::thread(test_ndping_send, dest, i, inbalanced_io_depth, flow_size, srcPort + i));
					
				} else {
					workers.push_back(std::thread(test_ndping_send, dest, i, io_depth, flow_size, srcPort + i));
				}
				if(pin == 1) {
					cpu_set_t cpuset;
					CPU_ZERO(&cpuset);
					if(thread_count == 1 || threads_per_core == 0) {
						if(sc == 2)
							CPU_SET(cpu_list[0], &cpuset);
						else {
							CPU_SET(cpu_list[(i * 2) % sc], &cpuset);
						}
					}
					else // threads_per_core = 2, sc = 26
						CPU_SET(cpu_list[(i / threads_per_core)%sc], &cpuset); // fix a small bug that could ping thread to core 0.
					pthread_setaffinity_np(workers[workers.size() - 1].native_handle(), sizeof(cpu_set_t), &cpuset);
				}	
				//workers.push_back(std::thread(test_ndping_recv, fd, dest, srcPort - 10000));
			} else if (strcmp(argv[nextArg], "tcppingpong") == 0) {
				fd = socket(AF_INET, SOCK_STREAM, 0);
				optval = 6;
				setsockopt(fd, SOL_SOCKET, SO_PRIORITY, &optval, unsigned(sizeof(optval)));  
				getsockopt(fd, SOL_SOCKET, SO_PRIORITY, &optval, &optlen);
				printf("optval:%d\n", optval);
				workers.push_back(std::thread(test_tcppingpong, fd, dest, i));
			} 
			 else {
				printf("Unknown operation '%s'\n", argv[nextArg]);
				exit(1);
			}
		}
	}
	
    std::this_thread::sleep_for (std::chrono::seconds(experiment_time));
	stop_count = 1;
	for(unsigned i = 0; i < workers.size(); i++) {
		workers[i].join();
	}
	lfile << get_mean_timehist(time_hist) << " " << estimate_percentile(time_hist, 0.99) << " " << estimate_percentile(time_hist, 0.999)  << std::endl; 
	lfile.close();
	hfile.write(reinterpret_cast<const char*>(time_hist.data()), time_hist.size() * sizeof(std::atomic<long long>));
	hfile.close();
	free(buffer);
	exit(0);
}

