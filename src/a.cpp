

struct Simple { // Category 0: trivial
  int is1;
  void s();
  int is2;
  Simple() { is1 = 69; }
}; // size 0x8

struct A : public Simple { // Category 1: leaf
  int ia1;
  virtual void f ();
  virtual void g ();
  virtual void h ();
  int ia2;
  A() { ia1 = 69; }
}; // size 0x8+0x8+0x4=0x14

struct SecondContainingVfs {
  int ise1;
  virtual void u ();
  virtual void v ();
  int ise2;
}; // size 0x4

void SecondContainingVfs::u() {}
void SecondContainingVfs::v() {}

struct ThirdContainingVfs {
  virtual void i ();
  virtual void j ();
}; // size 0x4

void ThirdContainingVfs::i() {}
void ThirdContainingVfs::j() {}

struct B: public virtual A {
  int ib1;
  void f ();
  void h ();
  int ib2;
  B() { ib1 = 69; }
}; // size 0x14(A)+0x8(data)+0x4(vtabp)+0x4(Aoff)+0x4(unk)=0x28

struct D: public virtual A, public ThirdContainingVfs {
  int id1;
  void f();
  void h();
  int id2;
  D() { id1 = 69; }
};

struct C: public A, public SecondContainingVfs { // Category 2: Non-virtual bases only
  int ic1;
  void f ();
  void h ();
  int ic2;
  C() { ic1 = 69; }
}; // size 0x14(A)+0x4(S)+0x8(data)=0x20

struct E: public B, public D, public virtual SecondContainingVfs {
  C c;
  B b;
  int ie1;
  void f();
  void h();
  int ie2;
  E() { ie1 = 69; }
};

void A::f() {}
void A::g() {}
void A::h() {}

void B::f() {}
void B::h() {}

void C::f() {}
void C::h() {}

void D::f() {}
void D::h() {}

void E::f() {}
void E::h() {}

int astuff() {
    A* pa = new A;
    pa->g();
    pa->ia1 = 1;
    pa->ia2 = 2;
    pa->is1 = 3;
    pa->is2 = 4;

    delete pa;
    return pa->ia2;
}

int bstuff() {
    B* pb = new B;
    pb->f();
    pb->g();
    pb->A::f();
    pb->ib1 = 3;
    pb->ib2 = 4;
    pb->ia1 = 5;
    pb->ia2 = 6;

    A* pab = pb;
    pab->f();
    pab->g();
    pab->ia1 = 7;
    pab->ia2 = 8;

    delete pb;
    return pb->ib1 + pab->ia1;
}

int cstuff() {
    C* pc = new C;
    pc->f();
    pc->g();
    pc->u();
    pc->A::f();
    pc->ic1 = 3;
    pc->ic2 = 4;
    pc->ia1 = 5;
    pc->ia2 = 6;

    A* pac = pc;
    pac->f();
    pac->g();
    pac->ia1 = 7;
    pac->ia2 = 8;

    delete pc;
    return pc->ic1 + pac->ia1;
}

int estuff() {
    E* pe = new E;
    pe->f();
    pe->g();
    pe->A::f();
    pe->i();
    pe->j();
    pe->u();
    pe->v();
    pe->ie1 = 3;
    pe->ie2 = 4;
    pe->ia1 = 5;
    pe->ia2 = 6;

    A* pae = pe;
    pae->f();
    pae->g();
    pae->ia1 = 7;
    pae->ia2 = 8;

    delete pe;
    return pe->ib1 + pae->ia1;
}

int main(int argc, char** argv) {
    return astuff() + bstuff();
}
