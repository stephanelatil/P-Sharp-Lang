class A{
	u64 number;

	A(char param){
		number = param;
	}
}
class B{ //auto constructor with field set
	u64 number = 6;
}

A var = new A('C');