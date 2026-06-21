package main

import "fmt"

func d(x int, y int) int {
	var r int
	r = x / y
	return r
}

func p(a []int) {
	for i := 0; i < len(a); i++ {
		fmt.Println(a[i])
	}
}

type s struct {
	n string
	a int
	e string
}

func (x s) g() string {
	return x.n
}

func mn() {
	var tmp = s{n: "test", a: 25, e: "t@t.com"}
	fmt.Println(d(10, 2))
	p([]int{1, 2, 3})
	fmt.Println(tmp.g())
}
