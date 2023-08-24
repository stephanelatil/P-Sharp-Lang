; ModuleID = 'gc.c'
source_filename = "gc.c"
target datalayout = "e-m:w-p270:32:32-p271:32:32-p272:64:64-i64:64-f80:128-n8:16:32:64-S128"
target triple = "x86_64-pc-windows-msvc19.37.32822"

%struct.PS_GC__object = type { i8*, i8, %struct.PS_GC__object**, i64 }
%struct.PS_GC__hashset = type { %struct.PS_GC__hashset_bucket**, i64, i64 }
%struct.PS_GC__hashset_bucket = type { %struct.PS_GC__object*, %struct.PS_GC__hashset_bucket* }
%struct.PS_GC__scopeRootVarsStack = type { %struct.PS_GC__scopeRootVarsStackItem* }
%struct.PS_GC__scopeRootVarsStackItem = type { %struct.PS_GC__rootVarList*, %struct.PS_GC__scopeRootVarsStackItem* }
%struct.PS_GC__rootVarList = type { i64, %struct.PS_GC__object** }

; Function Attrs: nofree nosync nounwind uwtable
define dso_local void @PS_GC__mark(%struct.PS_GC__object* noundef %0) local_unnamed_addr #0 {
  %2 = icmp eq %struct.PS_GC__object* %0, null
  br i1 %2, label %21, label %3

3:                                                ; preds = %1
  %4 = getelementptr inbounds %struct.PS_GC__object, %struct.PS_GC__object* %0, i64 0, i32 1
  %5 = load i8, i8* %4, align 8, !tbaa !4
  %6 = icmp eq i8 %5, 0
  br i1 %6, label %7, label %21

7:                                                ; preds = %3
  store i8 1, i8* %4, align 8, !tbaa !4
  %8 = getelementptr inbounds %struct.PS_GC__object, %struct.PS_GC__object* %0, i64 0, i32 3
  %9 = load i64, i64* %8, align 8, !tbaa !10
  %10 = icmp eq i64 %9, 0
  br i1 %10, label %21, label %11

11:                                               ; preds = %7
  %12 = getelementptr inbounds %struct.PS_GC__object, %struct.PS_GC__object* %0, i64 0, i32 2
  br label %13

13:                                               ; preds = %11, %13
  %14 = phi i64 [ 0, %11 ], [ %18, %13 ]
  %15 = load %struct.PS_GC__object**, %struct.PS_GC__object*** %12, align 8, !tbaa !11
  %16 = getelementptr inbounds %struct.PS_GC__object*, %struct.PS_GC__object** %15, i64 %14
  %17 = load %struct.PS_GC__object*, %struct.PS_GC__object** %16, align 8, !tbaa !12
  tail call void @PS_GC__mark(%struct.PS_GC__object* noundef %17)
  %18 = add nuw i64 %14, 1
  %19 = load i64, i64* %8, align 8, !tbaa !10
  %20 = icmp ult i64 %18, %19
  br i1 %20, label %13, label %21, !llvm.loop !13

21:                                               ; preds = %13, %7, %3, %1
  ret void
}

; Function Attrs: nofree norecurse nosync nounwind uwtable
define dso_local void @PS_GC__unmark_all(%struct.PS_GC__hashset* nocapture noundef readonly %0) local_unnamed_addr #1 {
  %2 = getelementptr inbounds %struct.PS_GC__hashset, %struct.PS_GC__hashset* %0, i64 0, i32 1
  %3 = load i64, i64* %2, align 8, !tbaa !15
  %4 = icmp eq i64 %3, 0
  br i1 %4, label %27, label %5

5:                                                ; preds = %1
  %6 = getelementptr inbounds %struct.PS_GC__hashset, %struct.PS_GC__hashset* %0, i64 0, i32 0
  %7 = load %struct.PS_GC__hashset_bucket**, %struct.PS_GC__hashset_bucket*** %6, align 8, !tbaa !17
  %8 = and i64 %3, 1
  %9 = icmp eq i64 %3, 1
  br i1 %9, label %12, label %10

10:                                               ; preds = %5
  %11 = and i64 %3, -2
  br label %28

12:                                               ; preds = %55, %5
  %13 = phi i64 [ 0, %5 ], [ %56, %55 ]
  %14 = icmp eq i64 %8, 0
  br i1 %14, label %27, label %15

15:                                               ; preds = %12
  %16 = getelementptr inbounds %struct.PS_GC__hashset_bucket*, %struct.PS_GC__hashset_bucket** %7, i64 %13
  %17 = load %struct.PS_GC__hashset_bucket*, %struct.PS_GC__hashset_bucket** %16, align 8, !tbaa !12
  %18 = icmp eq %struct.PS_GC__hashset_bucket* %17, null
  br i1 %18, label %27, label %19

19:                                               ; preds = %15, %19
  %20 = phi %struct.PS_GC__hashset_bucket* [ %25, %19 ], [ %17, %15 ]
  %21 = getelementptr inbounds %struct.PS_GC__hashset_bucket, %struct.PS_GC__hashset_bucket* %20, i64 0, i32 0
  %22 = load %struct.PS_GC__object*, %struct.PS_GC__object** %21, align 8, !tbaa !18
  %23 = getelementptr inbounds %struct.PS_GC__object, %struct.PS_GC__object* %22, i64 0, i32 1
  store i8 0, i8* %23, align 8, !tbaa !4
  %24 = getelementptr inbounds %struct.PS_GC__hashset_bucket, %struct.PS_GC__hashset_bucket* %20, i64 0, i32 1
  %25 = load %struct.PS_GC__hashset_bucket*, %struct.PS_GC__hashset_bucket** %24, align 8, !tbaa !12
  %26 = icmp eq %struct.PS_GC__hashset_bucket* %25, null
  br i1 %26, label %27, label %19, !llvm.loop !20

27:                                               ; preds = %12, %19, %15, %1
  ret void

28:                                               ; preds = %55, %10
  %29 = phi i64 [ 0, %10 ], [ %56, %55 ]
  %30 = phi i64 [ 0, %10 ], [ %57, %55 ]
  %31 = getelementptr inbounds %struct.PS_GC__hashset_bucket*, %struct.PS_GC__hashset_bucket** %7, i64 %29
  %32 = load %struct.PS_GC__hashset_bucket*, %struct.PS_GC__hashset_bucket** %31, align 8, !tbaa !12
  %33 = icmp eq %struct.PS_GC__hashset_bucket* %32, null
  br i1 %33, label %42, label %34

34:                                               ; preds = %28, %34
  %35 = phi %struct.PS_GC__hashset_bucket* [ %40, %34 ], [ %32, %28 ]
  %36 = getelementptr inbounds %struct.PS_GC__hashset_bucket, %struct.PS_GC__hashset_bucket* %35, i64 0, i32 0
  %37 = load %struct.PS_GC__object*, %struct.PS_GC__object** %36, align 8, !tbaa !18
  %38 = getelementptr inbounds %struct.PS_GC__object, %struct.PS_GC__object* %37, i64 0, i32 1
  store i8 0, i8* %38, align 8, !tbaa !4
  %39 = getelementptr inbounds %struct.PS_GC__hashset_bucket, %struct.PS_GC__hashset_bucket* %35, i64 0, i32 1
  %40 = load %struct.PS_GC__hashset_bucket*, %struct.PS_GC__hashset_bucket** %39, align 8, !tbaa !12
  %41 = icmp eq %struct.PS_GC__hashset_bucket* %40, null
  br i1 %41, label %42, label %34, !llvm.loop !20

42:                                               ; preds = %34, %28
  %43 = or i64 %29, 1
  %44 = getelementptr inbounds %struct.PS_GC__hashset_bucket*, %struct.PS_GC__hashset_bucket** %7, i64 %43
  %45 = load %struct.PS_GC__hashset_bucket*, %struct.PS_GC__hashset_bucket** %44, align 8, !tbaa !12
  %46 = icmp eq %struct.PS_GC__hashset_bucket* %45, null
  br i1 %46, label %55, label %47

47:                                               ; preds = %42, %47
  %48 = phi %struct.PS_GC__hashset_bucket* [ %53, %47 ], [ %45, %42 ]
  %49 = getelementptr inbounds %struct.PS_GC__hashset_bucket, %struct.PS_GC__hashset_bucket* %48, i64 0, i32 0
  %50 = load %struct.PS_GC__object*, %struct.PS_GC__object** %49, align 8, !tbaa !18
  %51 = getelementptr inbounds %struct.PS_GC__object, %struct.PS_GC__object* %50, i64 0, i32 1
  store i8 0, i8* %51, align 8, !tbaa !4
  %52 = getelementptr inbounds %struct.PS_GC__hashset_bucket, %struct.PS_GC__hashset_bucket* %48, i64 0, i32 1
  %53 = load %struct.PS_GC__hashset_bucket*, %struct.PS_GC__hashset_bucket** %52, align 8, !tbaa !12
  %54 = icmp eq %struct.PS_GC__hashset_bucket* %53, null
  br i1 %54, label %55, label %47, !llvm.loop !20

55:                                               ; preds = %47, %42
  %56 = add nuw i64 %29, 2
  %57 = add i64 %30, 2
  %58 = icmp eq i64 %57, %11
  br i1 %58, label %12, label %28, !llvm.loop !21
}

; Function Attrs: nounwind uwtable
define dso_local void @PS_GC__sweep(%struct.PS_GC__hashset* noundef %0) local_unnamed_addr #2 {
  %2 = getelementptr inbounds %struct.PS_GC__hashset, %struct.PS_GC__hashset* %0, i64 0, i32 1
  %3 = load i64, i64* %2, align 8, !tbaa !15
  %4 = icmp eq i64 %3, 0
  br i1 %4, label %7, label %5

5:                                                ; preds = %1
  %6 = getelementptr inbounds %struct.PS_GC__hashset, %struct.PS_GC__hashset* %0, i64 0, i32 0
  br label %8

7:                                                ; preds = %48, %1
  ret void

8:                                                ; preds = %5, %48
  %9 = phi i64 [ %3, %5 ], [ %49, %48 ]
  %10 = phi i64 [ 0, %5 ], [ %50, %48 ]
  %11 = load %struct.PS_GC__hashset_bucket**, %struct.PS_GC__hashset_bucket*** %6, align 8, !tbaa !17
  %12 = getelementptr inbounds %struct.PS_GC__hashset_bucket*, %struct.PS_GC__hashset_bucket** %11, i64 %10
  %13 = load %struct.PS_GC__hashset_bucket*, %struct.PS_GC__hashset_bucket** %12, align 8, !tbaa !12
  %14 = icmp eq %struct.PS_GC__hashset_bucket* %13, null
  br i1 %14, label %48, label %15

15:                                               ; preds = %8, %41
  %16 = phi %struct.PS_GC__hashset_bucket* [ %44, %41 ], [ %13, %8 ]
  %17 = phi %struct.PS_GC__hashset_bucket* [ %42, %41 ], [ null, %8 ]
  %18 = getelementptr inbounds %struct.PS_GC__hashset_bucket, %struct.PS_GC__hashset_bucket* %16, i64 0, i32 0
  %19 = load %struct.PS_GC__object*, %struct.PS_GC__object** %18, align 8, !tbaa !18
  %20 = getelementptr inbounds %struct.PS_GC__object, %struct.PS_GC__object* %19, i64 0, i32 1
  %21 = load i8, i8* %20, align 8, !tbaa !4
  %22 = icmp eq i8 %21, 0
  br i1 %22, label %23, label %41

23:                                               ; preds = %15
  %24 = icmp eq %struct.PS_GC__hashset_bucket* %17, null
  %25 = getelementptr inbounds %struct.PS_GC__hashset_bucket, %struct.PS_GC__hashset_bucket* %16, i64 0, i32 1
  %26 = load %struct.PS_GC__hashset_bucket*, %struct.PS_GC__hashset_bucket** %25, align 8, !tbaa !22
  br i1 %24, label %32, label %27

27:                                               ; preds = %23
  %28 = getelementptr inbounds %struct.PS_GC__hashset_bucket, %struct.PS_GC__hashset_bucket* %17, i64 0, i32 1
  store %struct.PS_GC__hashset_bucket* %26, %struct.PS_GC__hashset_bucket** %28, align 8, !tbaa !22
  %29 = tail call i32 @PS_GC__removeItem(%struct.PS_GC__hashset* noundef %0, %struct.PS_GC__object* noundef nonnull %19) #5
  %30 = getelementptr inbounds %struct.PS_GC__object, %struct.PS_GC__object* %19, i64 0, i32 0
  %31 = load i8*, i8** %30, align 8, !tbaa !23
  tail call void @free(i8* noundef %31) #5
  tail call void @PS_GC__delete_object(%struct.PS_GC__object* noundef nonnull %19) #5
  br label %39

32:                                               ; preds = %23
  %33 = load %struct.PS_GC__hashset_bucket**, %struct.PS_GC__hashset_bucket*** %6, align 8, !tbaa !17
  %34 = getelementptr inbounds %struct.PS_GC__hashset_bucket*, %struct.PS_GC__hashset_bucket** %33, i64 %10
  store %struct.PS_GC__hashset_bucket* %26, %struct.PS_GC__hashset_bucket** %34, align 8, !tbaa !12
  %35 = load %struct.PS_GC__object*, %struct.PS_GC__object** %18, align 8, !tbaa !18
  %36 = tail call i32 @PS_GC__removeItem(%struct.PS_GC__hashset* noundef %0, %struct.PS_GC__object* noundef %35) #5
  %37 = getelementptr inbounds %struct.PS_GC__object, %struct.PS_GC__object* %35, i64 0, i32 0
  %38 = load i8*, i8** %37, align 8, !tbaa !23
  tail call void @free(i8* noundef %38) #5
  tail call void @PS_GC__delete_object(%struct.PS_GC__object* noundef %35) #5
  br label %39

39:                                               ; preds = %32, %27
  %40 = phi %struct.PS_GC__hashset_bucket* [ null, %32 ], [ %17, %27 ]
  tail call void @PS_GC__delete_hashset_bucket(%struct.PS_GC__hashset_bucket* noundef nonnull %16) #5
  br label %41

41:                                               ; preds = %39, %15
  %42 = phi %struct.PS_GC__hashset_bucket* [ %16, %15 ], [ %40, %39 ]
  %43 = getelementptr inbounds %struct.PS_GC__hashset_bucket, %struct.PS_GC__hashset_bucket* %16, i64 0, i32 1
  %44 = load %struct.PS_GC__hashset_bucket*, %struct.PS_GC__hashset_bucket** %43, align 8, !tbaa !12
  %45 = icmp eq %struct.PS_GC__hashset_bucket* %44, null
  br i1 %45, label %46, label %15, !llvm.loop !24

46:                                               ; preds = %41
  %47 = load i64, i64* %2, align 8, !tbaa !15
  br label %48

48:                                               ; preds = %46, %8
  %49 = phi i64 [ %47, %46 ], [ %9, %8 ]
  %50 = add nuw i64 %10, 1
  %51 = icmp ult i64 %50, %49
  br i1 %51, label %8, label %7, !llvm.loop !25
}

; Function Attrs: nounwind uwtable
define dso_local void @PS_GC__collect_object(%struct.PS_GC__hashset* noundef %0, %struct.PS_GC__object* noundef %1) local_unnamed_addr #2 {
  %3 = tail call i32 @PS_GC__removeItem(%struct.PS_GC__hashset* noundef %0, %struct.PS_GC__object* noundef %1) #5
  %4 = getelementptr inbounds %struct.PS_GC__object, %struct.PS_GC__object* %1, i64 0, i32 0
  %5 = load i8*, i8** %4, align 8, !tbaa !23
  tail call void @free(i8* noundef %5)
  tail call void @PS_GC__delete_object(%struct.PS_GC__object* noundef %1) #5
  ret void
}

declare dso_local void @PS_GC__delete_hashset_bucket(%struct.PS_GC__hashset_bucket* noundef) local_unnamed_addr #3

declare dso_local i32 @PS_GC__removeItem(%struct.PS_GC__hashset* noundef, %struct.PS_GC__object* noundef) local_unnamed_addr #3

; Function Attrs: inaccessiblemem_or_argmemonly mustprogress nounwind willreturn
declare dso_local void @free(i8* nocapture noundef) local_unnamed_addr #4

declare dso_local void @PS_GC__delete_object(%struct.PS_GC__object* noundef) local_unnamed_addr #3

; Function Attrs: nounwind uwtable
define dso_local void @PS_GC__assign_var(%struct.PS_GC__scopeRootVarsStack* nocapture noundef readonly %0, %struct.PS_GC__hashset* noundef %1, i8* noundef %2, i32 noundef %3, i32 noundef %4) local_unnamed_addr #2 {
  %6 = getelementptr inbounds %struct.PS_GC__scopeRootVarsStack, %struct.PS_GC__scopeRootVarsStack* %0, i64 0, i32 0
  %7 = load %struct.PS_GC__scopeRootVarsStackItem*, %struct.PS_GC__scopeRootVarsStackItem** %6, align 8, !tbaa !12
  %8 = icmp sgt i32 %3, 0
  br i1 %8, label %9, label %49

9:                                                ; preds = %5
  %10 = add i32 %3, -1
  %11 = and i32 %3, 7
  %12 = icmp eq i32 %11, 0
  br i1 %12, label %22, label %13

13:                                               ; preds = %9, %13
  %14 = phi %struct.PS_GC__scopeRootVarsStackItem* [ %19, %13 ], [ %7, %9 ]
  %15 = phi i32 [ %18, %13 ], [ %3, %9 ]
  %16 = phi i32 [ %20, %13 ], [ 0, %9 ]
  %17 = getelementptr inbounds %struct.PS_GC__scopeRootVarsStackItem, %struct.PS_GC__scopeRootVarsStackItem* %14, i64 0, i32 1
  %18 = add nsw i32 %15, -1
  %19 = load %struct.PS_GC__scopeRootVarsStackItem*, %struct.PS_GC__scopeRootVarsStackItem** %17, align 8, !tbaa !12
  %20 = add i32 %16, 1
  %21 = icmp eq i32 %20, %11
  br i1 %21, label %22, label %13, !llvm.loop !26

22:                                               ; preds = %13, %9
  %23 = phi %struct.PS_GC__scopeRootVarsStackItem* [ %7, %9 ], [ %19, %13 ]
  %24 = phi i32 [ %3, %9 ], [ %18, %13 ]
  %25 = phi %struct.PS_GC__scopeRootVarsStackItem* [ undef, %9 ], [ %19, %13 ]
  %26 = icmp ult i32 %10, 7
  br i1 %26, label %49, label %27

27:                                               ; preds = %22, %27
  %28 = phi %struct.PS_GC__scopeRootVarsStackItem* [ %46, %27 ], [ %23, %22 ]
  %29 = phi i32 [ %45, %27 ], [ %24, %22 ]
  %30 = getelementptr inbounds %struct.PS_GC__scopeRootVarsStackItem, %struct.PS_GC__scopeRootVarsStackItem* %28, i64 0, i32 1
  %31 = load %struct.PS_GC__scopeRootVarsStackItem*, %struct.PS_GC__scopeRootVarsStackItem** %30, align 8, !tbaa !12
  %32 = getelementptr inbounds %struct.PS_GC__scopeRootVarsStackItem, %struct.PS_GC__scopeRootVarsStackItem* %31, i64 0, i32 1
  %33 = load %struct.PS_GC__scopeRootVarsStackItem*, %struct.PS_GC__scopeRootVarsStackItem** %32, align 8, !tbaa !12
  %34 = getelementptr inbounds %struct.PS_GC__scopeRootVarsStackItem, %struct.PS_GC__scopeRootVarsStackItem* %33, i64 0, i32 1
  %35 = load %struct.PS_GC__scopeRootVarsStackItem*, %struct.PS_GC__scopeRootVarsStackItem** %34, align 8, !tbaa !12
  %36 = getelementptr inbounds %struct.PS_GC__scopeRootVarsStackItem, %struct.PS_GC__scopeRootVarsStackItem* %35, i64 0, i32 1
  %37 = load %struct.PS_GC__scopeRootVarsStackItem*, %struct.PS_GC__scopeRootVarsStackItem** %36, align 8, !tbaa !12
  %38 = getelementptr inbounds %struct.PS_GC__scopeRootVarsStackItem, %struct.PS_GC__scopeRootVarsStackItem* %37, i64 0, i32 1
  %39 = load %struct.PS_GC__scopeRootVarsStackItem*, %struct.PS_GC__scopeRootVarsStackItem** %38, align 8, !tbaa !12
  %40 = getelementptr inbounds %struct.PS_GC__scopeRootVarsStackItem, %struct.PS_GC__scopeRootVarsStackItem* %39, i64 0, i32 1
  %41 = load %struct.PS_GC__scopeRootVarsStackItem*, %struct.PS_GC__scopeRootVarsStackItem** %40, align 8, !tbaa !12
  %42 = getelementptr inbounds %struct.PS_GC__scopeRootVarsStackItem, %struct.PS_GC__scopeRootVarsStackItem* %41, i64 0, i32 1
  %43 = load %struct.PS_GC__scopeRootVarsStackItem*, %struct.PS_GC__scopeRootVarsStackItem** %42, align 8, !tbaa !12
  %44 = getelementptr inbounds %struct.PS_GC__scopeRootVarsStackItem, %struct.PS_GC__scopeRootVarsStackItem* %43, i64 0, i32 1
  %45 = add nsw i32 %29, -8
  %46 = load %struct.PS_GC__scopeRootVarsStackItem*, %struct.PS_GC__scopeRootVarsStackItem** %44, align 8, !tbaa !12
  %47 = add i32 %29, -9
  %48 = icmp ult i32 %47, -2
  br i1 %48, label %27, label %49, !llvm.loop !28

49:                                               ; preds = %22, %27, %5
  %50 = phi %struct.PS_GC__scopeRootVarsStackItem* [ %7, %5 ], [ %25, %22 ], [ %46, %27 ]
  %51 = tail call %struct.PS_GC__object* @PS_GC__getItem(%struct.PS_GC__hashset* noundef %1, i8* noundef %2) #5
  %52 = getelementptr inbounds %struct.PS_GC__scopeRootVarsStackItem, %struct.PS_GC__scopeRootVarsStackItem* %50, i64 0, i32 0
  %53 = load %struct.PS_GC__rootVarList*, %struct.PS_GC__rootVarList** %52, align 8, !tbaa !29
  %54 = getelementptr inbounds %struct.PS_GC__rootVarList, %struct.PS_GC__rootVarList* %53, i64 0, i32 1
  %55 = load %struct.PS_GC__object**, %struct.PS_GC__object*** %54, align 8, !tbaa !31
  %56 = sext i32 %4 to i64
  %57 = getelementptr inbounds %struct.PS_GC__object*, %struct.PS_GC__object** %55, i64 %56
  store %struct.PS_GC__object* %51, %struct.PS_GC__object** %57, align 8, !tbaa !12
  ret void
}

declare dso_local %struct.PS_GC__object* @PS_GC__getItem(%struct.PS_GC__hashset* noundef, i8* noundef) local_unnamed_addr #3

; Function Attrs: nounwind uwtable
define dso_local %struct.PS_GC__object* @PC_GC__new_obj(%struct.PS_GC__hashset* noundef %0, i8* noundef %1) local_unnamed_addr #2 {
  %3 = tail call %struct.PS_GC__object* @PS_GC__create_obj(i8* noundef %1) #5
  %4 = tail call i32 @PS_GC__insertItem(%struct.PS_GC__hashset* noundef %0, %struct.PS_GC__object* noundef %3) #5
  ret %struct.PS_GC__object* %3
}

declare dso_local %struct.PS_GC__object* @PS_GC__create_obj(i8* noundef) local_unnamed_addr #3

declare dso_local i32 @PS_GC__insertItem(%struct.PS_GC__hashset* noundef, %struct.PS_GC__object* noundef) local_unnamed_addr #3

; Function Attrs: nounwind uwtable
define dso_local void @PS_GC__garbage_collect(%struct.PS_GC__scopeRootVarsStack* nocapture noundef readonly %0, %struct.PS_GC__hashset* noundef %1) local_unnamed_addr #2 {
  %3 = getelementptr inbounds %struct.PS_GC__scopeRootVarsStack, %struct.PS_GC__scopeRootVarsStack* %0, i64 0, i32 0
  %4 = load %struct.PS_GC__scopeRootVarsStackItem*, %struct.PS_GC__scopeRootVarsStackItem** %3, align 8, !tbaa !12
  %5 = icmp eq %struct.PS_GC__scopeRootVarsStackItem* %4, null
  br i1 %5, label %29, label %6

6:                                                ; preds = %2, %13
  %7 = phi %struct.PS_GC__scopeRootVarsStackItem* [ %15, %13 ], [ %4, %2 ]
  %8 = getelementptr inbounds %struct.PS_GC__scopeRootVarsStackItem, %struct.PS_GC__scopeRootVarsStackItem* %7, i64 0, i32 0
  %9 = load %struct.PS_GC__rootVarList*, %struct.PS_GC__rootVarList** %8, align 8, !tbaa !29
  %10 = getelementptr inbounds %struct.PS_GC__rootVarList, %struct.PS_GC__rootVarList* %9, i64 0, i32 0
  %11 = load i64, i64* %10, align 8, !tbaa !33
  %12 = icmp eq i64 %11, 0
  br i1 %12, label %13, label %17

13:                                               ; preds = %17, %6
  %14 = getelementptr inbounds %struct.PS_GC__scopeRootVarsStackItem, %struct.PS_GC__scopeRootVarsStackItem* %7, i64 0, i32 1
  %15 = load %struct.PS_GC__scopeRootVarsStackItem*, %struct.PS_GC__scopeRootVarsStackItem** %14, align 8, !tbaa !12
  %16 = icmp eq %struct.PS_GC__scopeRootVarsStackItem* %15, null
  br i1 %16, label %29, label %6, !llvm.loop !34

17:                                               ; preds = %6, %17
  %18 = phi %struct.PS_GC__rootVarList* [ %25, %17 ], [ %9, %6 ]
  %19 = phi i64 [ %24, %17 ], [ 0, %6 ]
  %20 = getelementptr inbounds %struct.PS_GC__rootVarList, %struct.PS_GC__rootVarList* %18, i64 0, i32 1
  %21 = load %struct.PS_GC__object**, %struct.PS_GC__object*** %20, align 8, !tbaa !31
  %22 = getelementptr inbounds %struct.PS_GC__object*, %struct.PS_GC__object** %21, i64 %19
  %23 = load %struct.PS_GC__object*, %struct.PS_GC__object** %22, align 8, !tbaa !12
  tail call void @PS_GC__mark(%struct.PS_GC__object* noundef %23)
  %24 = add nuw i64 %19, 1
  %25 = load %struct.PS_GC__rootVarList*, %struct.PS_GC__rootVarList** %8, align 8, !tbaa !29
  %26 = getelementptr inbounds %struct.PS_GC__rootVarList, %struct.PS_GC__rootVarList* %25, i64 0, i32 0
  %27 = load i64, i64* %26, align 8, !tbaa !33
  %28 = icmp ult i64 %24, %27
  br i1 %28, label %17, label %13, !llvm.loop !35

29:                                               ; preds = %13, %2
  tail call void @PS_GC__sweep(%struct.PS_GC__hashset* noundef %1)
  %30 = getelementptr inbounds %struct.PS_GC__hashset, %struct.PS_GC__hashset* %1, i64 0, i32 1
  %31 = load i64, i64* %30, align 8, !tbaa !15
  %32 = icmp eq i64 %31, 0
  br i1 %32, label %86, label %33

33:                                               ; preds = %29
  %34 = getelementptr inbounds %struct.PS_GC__hashset, %struct.PS_GC__hashset* %1, i64 0, i32 0
  %35 = load %struct.PS_GC__hashset_bucket**, %struct.PS_GC__hashset_bucket*** %34, align 8, !tbaa !17
  %36 = and i64 %31, 1
  %37 = icmp eq i64 %31, 1
  br i1 %37, label %71, label %38

38:                                               ; preds = %33
  %39 = and i64 %31, -2
  br label %40

40:                                               ; preds = %67, %38
  %41 = phi i64 [ 0, %38 ], [ %68, %67 ]
  %42 = phi i64 [ 0, %38 ], [ %69, %67 ]
  %43 = getelementptr inbounds %struct.PS_GC__hashset_bucket*, %struct.PS_GC__hashset_bucket** %35, i64 %41
  %44 = load %struct.PS_GC__hashset_bucket*, %struct.PS_GC__hashset_bucket** %43, align 8, !tbaa !12
  %45 = icmp eq %struct.PS_GC__hashset_bucket* %44, null
  br i1 %45, label %54, label %46

46:                                               ; preds = %40, %46
  %47 = phi %struct.PS_GC__hashset_bucket* [ %52, %46 ], [ %44, %40 ]
  %48 = getelementptr inbounds %struct.PS_GC__hashset_bucket, %struct.PS_GC__hashset_bucket* %47, i64 0, i32 0
  %49 = load %struct.PS_GC__object*, %struct.PS_GC__object** %48, align 8, !tbaa !18
  %50 = getelementptr inbounds %struct.PS_GC__object, %struct.PS_GC__object* %49, i64 0, i32 1
  store i8 0, i8* %50, align 8, !tbaa !4
  %51 = getelementptr inbounds %struct.PS_GC__hashset_bucket, %struct.PS_GC__hashset_bucket* %47, i64 0, i32 1
  %52 = load %struct.PS_GC__hashset_bucket*, %struct.PS_GC__hashset_bucket** %51, align 8, !tbaa !12
  %53 = icmp eq %struct.PS_GC__hashset_bucket* %52, null
  br i1 %53, label %54, label %46, !llvm.loop !20

54:                                               ; preds = %46, %40
  %55 = or i64 %41, 1
  %56 = getelementptr inbounds %struct.PS_GC__hashset_bucket*, %struct.PS_GC__hashset_bucket** %35, i64 %55
  %57 = load %struct.PS_GC__hashset_bucket*, %struct.PS_GC__hashset_bucket** %56, align 8, !tbaa !12
  %58 = icmp eq %struct.PS_GC__hashset_bucket* %57, null
  br i1 %58, label %67, label %59

59:                                               ; preds = %54, %59
  %60 = phi %struct.PS_GC__hashset_bucket* [ %65, %59 ], [ %57, %54 ]
  %61 = getelementptr inbounds %struct.PS_GC__hashset_bucket, %struct.PS_GC__hashset_bucket* %60, i64 0, i32 0
  %62 = load %struct.PS_GC__object*, %struct.PS_GC__object** %61, align 8, !tbaa !18
  %63 = getelementptr inbounds %struct.PS_GC__object, %struct.PS_GC__object* %62, i64 0, i32 1
  store i8 0, i8* %63, align 8, !tbaa !4
  %64 = getelementptr inbounds %struct.PS_GC__hashset_bucket, %struct.PS_GC__hashset_bucket* %60, i64 0, i32 1
  %65 = load %struct.PS_GC__hashset_bucket*, %struct.PS_GC__hashset_bucket** %64, align 8, !tbaa !12
  %66 = icmp eq %struct.PS_GC__hashset_bucket* %65, null
  br i1 %66, label %67, label %59, !llvm.loop !20

67:                                               ; preds = %59, %54
  %68 = add nuw i64 %41, 2
  %69 = add i64 %42, 2
  %70 = icmp eq i64 %69, %39
  br i1 %70, label %71, label %40, !llvm.loop !21

71:                                               ; preds = %67, %33
  %72 = phi i64 [ 0, %33 ], [ %68, %67 ]
  %73 = icmp eq i64 %36, 0
  br i1 %73, label %86, label %74

74:                                               ; preds = %71
  %75 = getelementptr inbounds %struct.PS_GC__hashset_bucket*, %struct.PS_GC__hashset_bucket** %35, i64 %72
  %76 = load %struct.PS_GC__hashset_bucket*, %struct.PS_GC__hashset_bucket** %75, align 8, !tbaa !12
  %77 = icmp eq %struct.PS_GC__hashset_bucket* %76, null
  br i1 %77, label %86, label %78

78:                                               ; preds = %74, %78
  %79 = phi %struct.PS_GC__hashset_bucket* [ %84, %78 ], [ %76, %74 ]
  %80 = getelementptr inbounds %struct.PS_GC__hashset_bucket, %struct.PS_GC__hashset_bucket* %79, i64 0, i32 0
  %81 = load %struct.PS_GC__object*, %struct.PS_GC__object** %80, align 8, !tbaa !18
  %82 = getelementptr inbounds %struct.PS_GC__object, %struct.PS_GC__object* %81, i64 0, i32 1
  store i8 0, i8* %82, align 8, !tbaa !4
  %83 = getelementptr inbounds %struct.PS_GC__hashset_bucket, %struct.PS_GC__hashset_bucket* %79, i64 0, i32 1
  %84 = load %struct.PS_GC__hashset_bucket*, %struct.PS_GC__hashset_bucket** %83, align 8, !tbaa !12
  %85 = icmp eq %struct.PS_GC__hashset_bucket* %84, null
  br i1 %85, label %86, label %78, !llvm.loop !20

86:                                               ; preds = %71, %78, %74, %29
  ret void
}

attributes #0 = { nofree nosync nounwind uwtable "frame-pointer"="none" "min-legal-vector-width"="0" "no-trapping-math"="true" "stack-protector-buffer-size"="8" "target-cpu"="x86-64" "target-features"="+cx8,+fxsr,+mmx,+sse,+sse2,+x87" "tune-cpu"="generic" }
attributes #1 = { nofree norecurse nosync nounwind uwtable "frame-pointer"="none" "min-legal-vector-width"="0" "no-trapping-math"="true" "stack-protector-buffer-size"="8" "target-cpu"="x86-64" "target-features"="+cx8,+fxsr,+mmx,+sse,+sse2,+x87" "tune-cpu"="generic" }
attributes #2 = { nounwind uwtable "frame-pointer"="none" "min-legal-vector-width"="0" "no-trapping-math"="true" "stack-protector-buffer-size"="8" "target-cpu"="x86-64" "target-features"="+cx8,+fxsr,+mmx,+sse,+sse2,+x87" "tune-cpu"="generic" }
attributes #3 = { "frame-pointer"="none" "no-trapping-math"="true" "stack-protector-buffer-size"="8" "target-cpu"="x86-64" "target-features"="+cx8,+fxsr,+mmx,+sse,+sse2,+x87" "tune-cpu"="generic" }
attributes #4 = { inaccessiblemem_or_argmemonly mustprogress nounwind willreturn "frame-pointer"="none" "no-trapping-math"="true" "stack-protector-buffer-size"="8" "target-cpu"="x86-64" "target-features"="+cx8,+fxsr,+mmx,+sse,+sse2,+x87" "tune-cpu"="generic" }
attributes #5 = { nounwind }

!llvm.module.flags = !{!0, !1, !2}
!llvm.ident = !{!3}

!0 = !{i32 1, !"wchar_size", i32 2}
!1 = !{i32 7, !"PIC Level", i32 2}
!2 = !{i32 7, !"uwtable", i32 1}
!3 = !{!"clang version 14.0.6"}
!4 = !{!5, !7, i64 8}
!5 = !{!"PS_GC__object", !6, i64 0, !7, i64 8, !6, i64 16, !9, i64 24}
!6 = !{!"any pointer", !7, i64 0}
!7 = !{!"omnipotent char", !8, i64 0}
!8 = !{!"Simple C/C++ TBAA"}
!9 = !{!"long long", !7, i64 0}
!10 = !{!5, !9, i64 24}
!11 = !{!5, !6, i64 16}
!12 = !{!6, !6, i64 0}
!13 = distinct !{!13, !14}
!14 = !{!"llvm.loop.mustprogress"}
!15 = !{!16, !9, i64 8}
!16 = !{!"PS_GC__hashset", !6, i64 0, !9, i64 8, !9, i64 16}
!17 = !{!16, !6, i64 0}
!18 = !{!19, !6, i64 0}
!19 = !{!"PS_GC__hashset_bucket", !6, i64 0, !6, i64 8}
!20 = distinct !{!20, !14}
!21 = distinct !{!21, !14}
!22 = !{!19, !6, i64 8}
!23 = !{!5, !6, i64 0}
!24 = distinct !{!24, !14}
!25 = distinct !{!25, !14}
!26 = distinct !{!26, !27}
!27 = !{!"llvm.loop.unroll.disable"}
!28 = distinct !{!28, !14}
!29 = !{!30, !6, i64 0}
!30 = !{!"PS_GC__scopeRootVarsStackItem", !6, i64 0, !6, i64 8}
!31 = !{!32, !6, i64 8}
!32 = !{!"PS_GC__rootVarList", !9, i64 0, !6, i64 8}
!33 = !{!32, !9, i64 0}
!34 = distinct !{!34, !14}
!35 = distinct !{!35, !14}
