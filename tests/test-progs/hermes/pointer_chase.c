/*
 * Chase a shuffled linked list that is much larger than the LLC, so that
 * most loads go off-chip. It uses no libc so that it builds without static
 * libraries:
 *
 *   gcc -O2 -static -nostdlib -fno-stack-protector -o pointer_chase \
 *       pointer_chase.c
 *
 * It must run in gem5, since it uses a gem5 pseudo instruction to reset the
 * stats once the list is ready.
 */

#define LINE_SIZE 64
#define NUM_NODES (1ul << 18) /* 16 MB */
#define NUM_HOPS (1ul << 19)

struct node
{
    struct node *next;
    char pad[LINE_SIZE - sizeof(struct node *)];
};

static struct node nodes[NUM_NODES] __attribute__((aligned(LINE_SIZE)));
static unsigned int order[NUM_NODES];

static unsigned long
next_random(void)
{
    static unsigned long state = 88172645463325252ul;

    state ^= state << 13;
    state ^= state >> 7;
    state ^= state << 17;
    return state;
}

static long
syscall3(long number, long arg0, long arg1, long arg2)
{
    long ret;

    __asm__ volatile("syscall"
                     : "=a"(ret)
                     : "a"(number), "D"(arg0), "S"(arg1), "d"(arg2)
                     : "rcx", "r11", "memory");
    return ret;
}

static void
m5_reset_stats(void)
{
    __asm__ volatile("xor %%edi, %%edi\n"
                     "xor %%esi, %%esi\n"
                     ".byte 0x0f, 0x04\n"
                     ".word 0x40\n"
                     : : : "rax", "rdi", "rsi", "memory");
}

static void
build_list(void)
{
    unsigned long i;

    for (i = 0; i < NUM_NODES; i++)
        order[i] = i;

    for (i = NUM_NODES - 1; i > 0; i--) {
        unsigned long j = next_random() % (i + 1);
        unsigned int tmp = order[i];

        order[i] = order[j];
        order[j] = tmp;
    }

    for (i = 0; i < NUM_NODES; i++)
        nodes[order[i]].next = &nodes[order[(i + 1) % NUM_NODES]];
}

static void
print_hex(unsigned long value)
{
    static const char digits[] = "0123456789abcdef";
    char text[17];
    int i;

    for (i = 15; i >= 0; i--) {
        text[i] = digits[value & 0xf];
        value >>= 4;
    }
    text[16] = '\n';

    syscall3(1, 1, (long)text, sizeof(text));
}

void
chase_main(void)
{
    struct node *node = &nodes[0];
    unsigned long sum = 0;
    unsigned long i;

    build_list();
    m5_reset_stats();

    for (i = 0; i < NUM_HOPS; i++) {
        node = node->next;
        sum += (unsigned long)node;
    }

    print_hex(sum);
    syscall3(231, 0, 0, 0);
}

__asm__(".global _start\n"
        "_start:\n"
        "and $-16, %rsp\n"
        "call chase_main\n");
