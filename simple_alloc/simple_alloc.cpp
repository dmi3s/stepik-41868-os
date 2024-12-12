#include <cstddef>
#include <cassert>

struct tag {
    size_t size: 63;  // Total block size in bytes
    bool busy: 1;
};

namespace mem {
    tag* begin;
    tag* end;
}

inline tag* head(tag* tail) {
    char* h = reinterpret_cast<char*>(tail + 1) - tail->size;
    return reinterpret_cast<tag*>(h);
}

inline tag* tail(tag* head) {
    assert(head != mem::end);
    char* pt = reinterpret_cast<char*>(head) + head->size;
    return reinterpret_cast<tag*>(pt) - 1;
}

inline tag* prev_tail(tag* head) {
    assert(head != mem::begin);
    return head - 1;
}

inline tag* next(tag* head) {
    assert(head != mem::end);
    tag* pn = reinterpret_cast<tag *>(reinterpret_cast<char*>(head) + head->size);
    return pn;
}

inline tag* prev(tag* hd) {
    assert(hd != mem::begin);
    return head(prev_tail(hd));
}

inline void* user_mem(tag* head) {
    assert(head != mem::end);
    void* pv = reinterpret_cast<void*>(head + 1);
    return pv;
}

inline tag* from_user_mem(void* p) {
    return reinterpret_cast<tag*>(p) - 1;
}

void mysetup(void *buf, std::size_t size)
{
    static_assert(sizeof(tag) == 8, "sizeof(tag) == 8");

    tag* r = reinterpret_cast<tag*>(buf);
    *r = {size, false};
    *tail(r) = *r;
    mem::begin = r;
    mem::end = next(r);
}

// Функция аллокации
void *myalloc(std::size_t sz) {
    if (sz == 0)
        return nullptr;

    tag* block = mem::begin;
    const size_t size = ((sz + sizeof(tag) * 2 + 7) / 8) * 8;

    // Traverse the memory ptrs to find a suitable block
    while (block != mem::end) {
        if (!block->busy) { // Check if the block is free
            if (block->size >= size && block->size <= size + sizeof(tag) * 4) {
                // Mark the block as busy and return its user memory
                tag* t = tail(block);
                t->busy = block->busy = true;
                return user_mem(block);
            } else if (block->size > size) {
                // Split the block into a new block and allocate the requested size
                // Leave free block on the "left" side of the list to speed up next
                // call to myalloc()
                const size_t rest_size = block->size - size;
                block->size = rest_size;
                *tail(block) = *block;
                tag* new_block = next(block);
                *new_block = {size, true};
                *tail(new_block) = *new_block;
                return user_mem(new_block);
            }
        }
        // Move to the next block
        block = next(block);
    }

    // Return nullptr if no suitable block was found
    return nullptr;
}


// Функция освобождения
// This function frees the memory block allocated by myalloc().
// It takes a pointer to the user-accessible portion of the memory block as an argument.
void myfree(void *p)
{
    if (p == nullptr) return;
    
    assert(p >= mem::begin && p < mem::end);
    if (p<mem::begin || p>= mem::end) return;

    tag* block = from_user_mem(p);
    assert(block->busy);
    if (!block->busy) return;

    block->busy = false;
    *tail(block) = *block;

    // Try union prev block
    if (block != mem::begin) {
        tag* prv = prev(block);
        if (!prv->busy) {
            prv->size += block->size;
            *tail(prv) = *prv;
            block = prv;
        }
    }

    // Try union next block
    tag* nxt = next(block);
    if (nxt != mem::end && !nxt->busy) {
        block->size += nxt->size;
        *tail(block) = *block;
    }
}


///////////////////////////////////////////////////////////////////////////////

#include <stdio.h>

// Dumps the current state of the memory blocks.
void mydump() {
#if !defined(NDEBUG)
    for(tag* p = mem::begin; p != mem::end; p = next(p)) {
        printf("%8p  %10lu   %c\n", (void*)p, p->size, p->busy ? '+' : '-');
    }
#endif
}

#include <memory>
#include <cstring>
#include <chrono>

namespace {
    auto my_allocator = [](size_t sz) -> void* {
        void* const p = myalloc(sz);
        printf("\n>>> alloc(%lu) -> %p\n", sz, p);
        mydump();
        return p;
    };

    auto my_deleter = [](void* my_ptr) {
        myfree(my_ptr);
        printf("\n<<< free(%p)\n", my_ptr);
        mydump();
    };
}

void test_myalloc() {
    const size_t buffer_size = 1024;
    char buffer[buffer_size];

    // Setup memory allocator
    mysetup(buffer, buffer_size);
    mydump();

    // Test allocation of a small block
    void* p1 = my_allocator(16);
    assert(p1 != nullptr);
    memset(p1, 0, 16); // Test writing to allocated memory

    // Test allocation of a large block
    void* p2 = my_allocator(512);
    assert(p2 != nullptr);
    memset(p2, 0, 512);

    // Test allocation of a block too large to fit
    void* p3 = my_allocator(buffer_size);
    assert(p3 == nullptr);

    p3 = my_allocator(12);
    assert(p3 != nullptr);
    memset(p3, 0, 12);

    my_deleter(p1);
    my_deleter(p2);
    my_deleter(p3);
    p1 = my_allocator(buffer_size - sizeof(tag) * 2);
    my_deleter(p1);
}

uint64_t get_us() {
    return std::chrono::duration_cast<std::chrono::microseconds>(
        std::chrono::high_resolution_clock::now().time_since_epoch())
        .count();
}

void run() {
    auto dt = get_us();
    test_myalloc();
    dt = get_us() - dt;
    printf("Totla time: %lu ms\n", dt);
}


int main() {
    run();
}
