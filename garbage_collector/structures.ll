; ModuleID = 'structures.c'
source_filename = "structures.c"
target datalayout = "e-m:w-p270:32:32-p271:32:32-p272:64:64-i64:64-f80:128-n8:16:32:64-S128"
target triple = "x86_64-pc-windows-msvc19.37.32822"

%struct.PS_GC__scopeRootVarsStack = type { %struct.PS_GC__scopeRootVarsStackItem* }
%struct.PS_GC__scopeRootVarsStackItem = type { %struct.PS_GC__rootVarList*, %struct.PS_GC__scopeRootVarsStackItem* }
%struct.PS_GC__rootVarList = type { i64, %struct.PS_GC__object** }
%struct.PS_GC__object = type { i8*, i8, %struct.PS_GC__object**, i64 }
%struct.PS_GC__hashset = type { %struct.PS_GC__hashset_bucket**, i64, i64 }
%struct.PS_GC__hashset_bucket = type { %struct.PS_GC__object*, %struct.PS_GC__hashset_bucket* }

; Function Attrs: mustprogress nofree nounwind uwtable willreturn
define dso_local noalias %struct.PS_GC__scopeRootVarsStack* @PS_GC__initialize_stack() local_unnamed_addr #0 {
  %1 = tail call noalias dereferenceable_or_null(8) i8* @malloc(i64 noundef 8)
  %2 = bitcast i8* %1 to %struct.PS_GC__scopeRootVarsStack*
  %3 = icmp eq i8* %1, null
  br i1 %3, label %6, label %4

4:                                                ; preds = %0
  %5 = getelementptr inbounds %struct.PS_GC__scopeRootVarsStack, %struct.PS_GC__scopeRootVarsStack* %2, i64 0, i32 0
  store %struct.PS_GC__scopeRootVarsStackItem* null, %struct.PS_GC__scopeRootVarsStackItem** %5, align 8, !tbaa !4
  br label %6

6:                                                ; preds = %0, %4
  %7 = phi %struct.PS_GC__scopeRootVarsStack* [ %2, %4 ], [ null, %0 ]
  ret %struct.PS_GC__scopeRootVarsStack* %7
}

; Function Attrs: inaccessiblememonly mustprogress nofree nounwind willreturn
declare dso_local noalias noundef i8* @malloc(i64 noundef) local_unnamed_addr #1

; Function Attrs: mustprogress nofree nounwind uwtable willreturn
define dso_local noalias %struct.PS_GC__scopeRootVarsStackItem* @PS_GC__initialize_stack_item(%struct.PS_GC__scopeRootVarsStackItem* noundef %0, %struct.PS_GC__rootVarList* noundef %1) local_unnamed_addr #0 {
  %3 = tail call noalias dereferenceable_or_null(16) i8* @malloc(i64 noundef 16)
  %4 = bitcast i8* %3 to %struct.PS_GC__scopeRootVarsStackItem*
  %5 = icmp eq i8* %3, null
  br i1 %5, label %9, label %6

6:                                                ; preds = %2
  %7 = getelementptr inbounds %struct.PS_GC__scopeRootVarsStackItem, %struct.PS_GC__scopeRootVarsStackItem* %4, i64 0, i32 0
  store %struct.PS_GC__rootVarList* %1, %struct.PS_GC__rootVarList** %7, align 8, !tbaa !9
  %8 = getelementptr inbounds %struct.PS_GC__scopeRootVarsStackItem, %struct.PS_GC__scopeRootVarsStackItem* %4, i64 0, i32 1
  store %struct.PS_GC__scopeRootVarsStackItem* %0, %struct.PS_GC__scopeRootVarsStackItem** %8, align 8, !tbaa !11
  br label %9

9:                                                ; preds = %2, %6
  %10 = phi %struct.PS_GC__scopeRootVarsStackItem* [ %4, %6 ], [ null, %2 ]
  ret %struct.PS_GC__scopeRootVarsStackItem* %10
}

; Function Attrs: nounwind uwtable
define dso_local noalias %struct.PS_GC__hashset* @PS_GC__initialize_hashset(i64 noundef %0) local_unnamed_addr #2 {
  %2 = icmp eq i64 %0, 0
  br i1 %2, label %25, label %3

3:                                                ; preds = %1
  %4 = add i64 %0, -1
  %5 = icmp eq i64 %4, 0
  br i1 %5, label %12, label %6

6:                                                ; preds = %3, %6
  %7 = phi i64 [ %10, %6 ], [ 1, %3 ]
  %8 = phi i64 [ %9, %6 ], [ %4, %3 ]
  %9 = lshr i64 %8, 1
  %10 = shl i64 %7, 1
  %11 = icmp ult i64 %8, 2
  br i1 %11, label %12, label %6, !llvm.loop !12

12:                                               ; preds = %6, %3
  %13 = phi i64 [ 1, %3 ], [ %10, %6 ]
  %14 = tail call noalias dereferenceable_or_null(24) i8* @malloc(i64 noundef 24)
  %15 = bitcast i8* %14 to %struct.PS_GC__hashset*
  %16 = icmp eq i8* %14, null
  br i1 %16, label %25, label %17

17:                                               ; preds = %12
  %18 = getelementptr inbounds %struct.PS_GC__hashset, %struct.PS_GC__hashset* %15, i64 0, i32 1
  store i64 %13, i64* %18, align 8, !tbaa !14
  %19 = add i64 %13, -1
  %20 = getelementptr inbounds %struct.PS_GC__hashset, %struct.PS_GC__hashset* %15, i64 0, i32 2
  store i64 %19, i64* %20, align 8, !tbaa !17
  %21 = tail call noalias i8* @calloc(i64 noundef %13, i64 noundef 8)
  %22 = bitcast i8* %14 to i8**
  store i8* %21, i8** %22, align 8, !tbaa !18
  %23 = icmp eq i8* %21, null
  br i1 %23, label %24, label %25

24:                                               ; preds = %17
  tail call void @free(i8* noundef nonnull %14)
  br label %25

25:                                               ; preds = %24, %12, %17, %1
  %26 = phi %struct.PS_GC__hashset* [ null, %1 ], [ null, %24 ], [ null, %12 ], [ %15, %17 ]
  ret %struct.PS_GC__hashset* %26
}

; Function Attrs: inaccessiblememonly mustprogress nofree nounwind willreturn
declare dso_local noalias noundef i8* @calloc(i64 noundef, i64 noundef) local_unnamed_addr #1

; Function Attrs: inaccessiblemem_or_argmemonly mustprogress nounwind willreturn
declare dso_local void @free(i8* nocapture noundef) local_unnamed_addr #3

; Function Attrs: mustprogress nofree nounwind uwtable willreturn
define dso_local noalias %struct.PS_GC__hashset_bucket* @PS_GC__create_hashset_bucket(%struct.PS_GC__object* noundef %0) local_unnamed_addr #0 {
  %2 = tail call noalias dereferenceable_or_null(16) i8* @malloc(i64 noundef 16)
  %3 = bitcast i8* %2 to %struct.PS_GC__hashset_bucket*
  %4 = icmp eq i8* %2, null
  br i1 %4, label %8, label %5

5:                                                ; preds = %1
  %6 = getelementptr inbounds %struct.PS_GC__hashset_bucket, %struct.PS_GC__hashset_bucket* %3, i64 0, i32 1
  store %struct.PS_GC__hashset_bucket* null, %struct.PS_GC__hashset_bucket** %6, align 8, !tbaa !19
  %7 = getelementptr inbounds %struct.PS_GC__hashset_bucket, %struct.PS_GC__hashset_bucket* %3, i64 0, i32 0
  store %struct.PS_GC__object* %0, %struct.PS_GC__object** %7, align 8, !tbaa !21
  br label %8

8:                                                ; preds = %1, %5
  %9 = phi %struct.PS_GC__hashset_bucket* [ %3, %5 ], [ null, %1 ]
  ret %struct.PS_GC__hashset_bucket* %9
}

; Function Attrs: mustprogress nofree nounwind uwtable willreturn
define dso_local noalias %struct.PS_GC__object* @PS_GC__create_obj(i8* noundef %0) local_unnamed_addr #0 {
  %2 = tail call noalias dereferenceable_or_null(32) i8* @malloc(i64 noundef 32)
  %3 = bitcast i8* %2 to %struct.PS_GC__object*
  %4 = icmp eq i8* %2, null
  br i1 %4, label %10, label %5

5:                                                ; preds = %1
  %6 = getelementptr inbounds %struct.PS_GC__object, %struct.PS_GC__object* %3, i64 0, i32 0
  store i8* %0, i8** %6, align 8, !tbaa !22
  %7 = getelementptr inbounds %struct.PS_GC__object, %struct.PS_GC__object* %3, i64 0, i32 1
  store i8 0, i8* %7, align 8, !tbaa !24
  %8 = getelementptr inbounds %struct.PS_GC__object, %struct.PS_GC__object* %3, i64 0, i32 2
  %9 = bitcast %struct.PS_GC__object*** %8 to i8*
  call void @llvm.memset.p0i8.i64(i8* noundef nonnull align 8 dereferenceable(16) %9, i8 0, i64 16, i1 false)
  br label %10

10:                                               ; preds = %1, %5
  %11 = phi %struct.PS_GC__object* [ %3, %5 ], [ null, %1 ]
  ret %struct.PS_GC__object* %11
}

; Function Attrs: mustprogress nofree norecurse nosync nounwind uwtable willreturn writeonly
define dso_local void @PS_GC__add_children(%struct.PS_GC__object* nocapture noundef writeonly %0, %struct.PS_GC__object** noundef %1, i64 noundef %2) local_unnamed_addr #4 {
  %4 = getelementptr inbounds %struct.PS_GC__object, %struct.PS_GC__object* %0, i64 0, i32 2
  store %struct.PS_GC__object** %1, %struct.PS_GC__object*** %4, align 8, !tbaa !25
  %5 = getelementptr inbounds %struct.PS_GC__object, %struct.PS_GC__object* %0, i64 0, i32 3
  store i64 %2, i64* %5, align 8, !tbaa !26
  ret void
}

; Function Attrs: mustprogress nounwind uwtable willreturn
define dso_local noalias %struct.PS_GC__rootVarList* @PS_GC__create_rootVarList(i64 noundef %0) local_unnamed_addr #5 {
  %2 = tail call noalias dereferenceable_or_null(16) i8* @malloc(i64 noundef 16)
  %3 = bitcast i8* %2 to %struct.PS_GC__rootVarList*
  %4 = icmp eq i8* %2, null
  br i1 %4, label %12, label %5

5:                                                ; preds = %1
  %6 = getelementptr inbounds %struct.PS_GC__rootVarList, %struct.PS_GC__rootVarList* %3, i64 0, i32 0
  store i64 %0, i64* %6, align 8, !tbaa !27
  %7 = tail call noalias i8* @calloc(i64 noundef %0, i64 noundef 8)
  %8 = getelementptr inbounds %struct.PS_GC__rootVarList, %struct.PS_GC__rootVarList* %3, i64 0, i32 1
  %9 = bitcast %struct.PS_GC__object*** %8 to i8**
  store i8* %7, i8** %9, align 8, !tbaa !29
  %10 = icmp eq i8* %7, null
  br i1 %10, label %11, label %12

11:                                               ; preds = %5
  tail call void @free(i8* noundef nonnull %2)
  br label %12

12:                                               ; preds = %5, %1, %11
  %13 = phi %struct.PS_GC__rootVarList* [ null, %11 ], [ null, %1 ], [ %3, %5 ]
  ret %struct.PS_GC__rootVarList* %13
}

; Function Attrs: mustprogress nounwind uwtable willreturn
define dso_local void @PS_GC__delete_hashset_bucket(%struct.PS_GC__hashset_bucket* nocapture noundef %0) local_unnamed_addr #5 {
  %2 = bitcast %struct.PS_GC__hashset_bucket* %0 to i8*
  tail call void @free(i8* noundef %2)
  ret void
}

; Function Attrs: nounwind uwtable
define dso_local void @PS_GC__delete_stack(%struct.PS_GC__scopeRootVarsStack* nocapture noundef %0) local_unnamed_addr #2 {
  %2 = getelementptr inbounds %struct.PS_GC__scopeRootVarsStack, %struct.PS_GC__scopeRootVarsStack* %0, i64 0, i32 0
  %3 = load %struct.PS_GC__scopeRootVarsStackItem*, %struct.PS_GC__scopeRootVarsStackItem** %2, align 8, !tbaa !4
  %4 = icmp eq %struct.PS_GC__scopeRootVarsStackItem* %3, null
  br i1 %4, label %18, label %5

5:                                                ; preds = %1, %5
  %6 = phi %struct.PS_GC__scopeRootVarsStackItem* [ %16, %5 ], [ %3, %1 ]
  %7 = getelementptr inbounds %struct.PS_GC__scopeRootVarsStackItem, %struct.PS_GC__scopeRootVarsStackItem* %6, i64 0, i32 1
  %8 = load %struct.PS_GC__scopeRootVarsStackItem*, %struct.PS_GC__scopeRootVarsStackItem** %7, align 8, !tbaa !11
  store %struct.PS_GC__scopeRootVarsStackItem* %8, %struct.PS_GC__scopeRootVarsStackItem** %2, align 8, !tbaa !4
  %9 = getelementptr inbounds %struct.PS_GC__scopeRootVarsStackItem, %struct.PS_GC__scopeRootVarsStackItem* %6, i64 0, i32 0
  %10 = load %struct.PS_GC__rootVarList*, %struct.PS_GC__rootVarList** %9, align 8, !tbaa !9
  %11 = bitcast %struct.PS_GC__scopeRootVarsStackItem* %6 to i8*
  tail call void @free(i8* noundef %11) #10
  %12 = getelementptr inbounds %struct.PS_GC__rootVarList, %struct.PS_GC__rootVarList* %10, i64 0, i32 1
  %13 = bitcast %struct.PS_GC__object*** %12 to i8**
  %14 = load i8*, i8** %13, align 8, !tbaa !29
  tail call void @free(i8* noundef %14) #10
  %15 = bitcast %struct.PS_GC__rootVarList* %10 to i8*
  tail call void @free(i8* noundef %15) #10
  %16 = load %struct.PS_GC__scopeRootVarsStackItem*, %struct.PS_GC__scopeRootVarsStackItem** %2, align 8, !tbaa !4
  %17 = icmp eq %struct.PS_GC__scopeRootVarsStackItem* %16, null
  br i1 %17, label %18, label %5, !llvm.loop !30

18:                                               ; preds = %5, %1
  %19 = bitcast %struct.PS_GC__scopeRootVarsStack* %0 to i8*
  tail call void @free(i8* noundef %19)
  ret void
}

; Function Attrs: mustprogress nofree norecurse nosync nounwind readonly uwtable willreturn
define dso_local i32 @PS_GC__stack_is_empty(%struct.PS_GC__scopeRootVarsStack* nocapture noundef readonly %0) local_unnamed_addr #6 {
  %2 = getelementptr inbounds %struct.PS_GC__scopeRootVarsStack, %struct.PS_GC__scopeRootVarsStack* %0, i64 0, i32 0
  %3 = load %struct.PS_GC__scopeRootVarsStackItem*, %struct.PS_GC__scopeRootVarsStackItem** %2, align 8, !tbaa !4
  %4 = icmp eq %struct.PS_GC__scopeRootVarsStackItem* %3, null
  %5 = zext i1 %4 to i32
  ret i32 %5
}

; Function Attrs: mustprogress nounwind uwtable willreturn
define dso_local void @PS_GC__delete_rootVarList(%struct.PS_GC__rootVarList* nocapture noundef %0) local_unnamed_addr #5 {
  %2 = getelementptr inbounds %struct.PS_GC__rootVarList, %struct.PS_GC__rootVarList* %0, i64 0, i32 1
  %3 = bitcast %struct.PS_GC__object*** %2 to i8**
  %4 = load i8*, i8** %3, align 8, !tbaa !29
  tail call void @free(i8* noundef %4)
  %5 = bitcast %struct.PS_GC__rootVarList* %0 to i8*
  tail call void @free(i8* noundef %5)
  ret void
}

; Function Attrs: mustprogress nounwind uwtable willreturn
define dso_local %struct.PS_GC__rootVarList* @PS_GC__stack_pop(%struct.PS_GC__scopeRootVarsStack* nocapture noundef %0) local_unnamed_addr #5 {
  %2 = getelementptr inbounds %struct.PS_GC__scopeRootVarsStack, %struct.PS_GC__scopeRootVarsStack* %0, i64 0, i32 0
  %3 = load %struct.PS_GC__scopeRootVarsStackItem*, %struct.PS_GC__scopeRootVarsStackItem** %2, align 8, !tbaa !4
  %4 = icmp eq %struct.PS_GC__scopeRootVarsStackItem* %3, null
  br i1 %4, label %11, label %5

5:                                                ; preds = %1
  %6 = getelementptr inbounds %struct.PS_GC__scopeRootVarsStackItem, %struct.PS_GC__scopeRootVarsStackItem* %3, i64 0, i32 1
  %7 = load %struct.PS_GC__scopeRootVarsStackItem*, %struct.PS_GC__scopeRootVarsStackItem** %6, align 8, !tbaa !11
  store %struct.PS_GC__scopeRootVarsStackItem* %7, %struct.PS_GC__scopeRootVarsStackItem** %2, align 8, !tbaa !4
  %8 = getelementptr inbounds %struct.PS_GC__scopeRootVarsStackItem, %struct.PS_GC__scopeRootVarsStackItem* %3, i64 0, i32 0
  %9 = load %struct.PS_GC__rootVarList*, %struct.PS_GC__rootVarList** %8, align 8, !tbaa !9
  %10 = bitcast %struct.PS_GC__scopeRootVarsStackItem* %3 to i8*
  tail call void @free(i8* noundef %10) #10
  br label %11

11:                                               ; preds = %1, %5
  %12 = phi %struct.PS_GC__rootVarList* [ %9, %5 ], [ null, %1 ]
  ret %struct.PS_GC__rootVarList* %12
}

; Function Attrs: mustprogress nounwind uwtable willreturn
define dso_local void @PS_GC__delete_stack_item(%struct.PS_GC__scopeRootVarsStackItem* nocapture noundef %0) local_unnamed_addr #5 {
  %2 = bitcast %struct.PS_GC__scopeRootVarsStackItem* %0 to i8*
  tail call void @free(i8* noundef %2)
  ret void
}

; Function Attrs: mustprogress nounwind uwtable willreturn
define dso_local void @PS_GC__delete_object(%struct.PS_GC__object* nocapture noundef %0) local_unnamed_addr #5 {
  %2 = bitcast %struct.PS_GC__object* %0 to i8*
  tail call void @free(i8* noundef %2)
  ret void
}

; Function Attrs: nounwind uwtable
define dso_local void @PS_GC__delete_hashSet(%struct.PS_GC__hashset* nocapture noundef %0) local_unnamed_addr #2 {
  %2 = getelementptr inbounds %struct.PS_GC__hashset, %struct.PS_GC__hashset* %0, i64 0, i32 1
  %3 = load i64, i64* %2, align 8, !tbaa !14
  %4 = icmp eq i64 %3, 0
  br i1 %4, label %7, label %5

5:                                                ; preds = %1
  %6 = getelementptr inbounds %struct.PS_GC__hashset, %struct.PS_GC__hashset* %0, i64 0, i32 0
  br label %11

7:                                                ; preds = %11, %1
  %8 = bitcast %struct.PS_GC__hashset* %0 to i8**
  %9 = load i8*, i8** %8, align 8, !tbaa !18
  tail call void @free(i8* noundef %9)
  %10 = bitcast %struct.PS_GC__hashset* %0 to i8*
  tail call void @free(i8* noundef %10)
  ret void

11:                                               ; preds = %5, %11
  %12 = phi i64 [ 0, %5 ], [ %17, %11 ]
  %13 = load %struct.PS_GC__hashset_bucket**, %struct.PS_GC__hashset_bucket*** %6, align 8, !tbaa !18
  %14 = getelementptr inbounds %struct.PS_GC__hashset_bucket*, %struct.PS_GC__hashset_bucket** %13, i64 %12
  %15 = bitcast %struct.PS_GC__hashset_bucket** %14 to i8**
  %16 = load i8*, i8** %15, align 8, !tbaa !31
  tail call void @free(i8* noundef %16)
  %17 = add nuw i64 %12, 1
  %18 = load i64, i64* %2, align 8, !tbaa !14
  %19 = icmp ult i64 %17, %18
  br i1 %19, label %11, label %7, !llvm.loop !32
}

; Function Attrs: mustprogress nofree nounwind uwtable willreturn
define dso_local i32 @PS_GC__stack_push(%struct.PS_GC__scopeRootVarsStack* nocapture noundef %0, %struct.PS_GC__rootVarList* noundef %1) local_unnamed_addr #0 {
  %3 = icmp eq %struct.PS_GC__rootVarList* %1, null
  br i1 %3, label %14, label %4

4:                                                ; preds = %2
  %5 = tail call noalias dereferenceable_or_null(16) i8* @malloc(i64 noundef 16)
  %6 = bitcast i8* %5 to %struct.PS_GC__scopeRootVarsStackItem*
  %7 = icmp eq i8* %5, null
  br i1 %7, label %14, label %8

8:                                                ; preds = %4
  %9 = getelementptr inbounds %struct.PS_GC__scopeRootVarsStackItem, %struct.PS_GC__scopeRootVarsStackItem* %6, i64 0, i32 0
  store %struct.PS_GC__rootVarList* %1, %struct.PS_GC__rootVarList** %9, align 8, !tbaa !9
  %10 = getelementptr inbounds %struct.PS_GC__scopeRootVarsStack, %struct.PS_GC__scopeRootVarsStack* %0, i64 0, i32 0
  %11 = load %struct.PS_GC__scopeRootVarsStackItem*, %struct.PS_GC__scopeRootVarsStackItem** %10, align 8, !tbaa !4
  %12 = getelementptr inbounds %struct.PS_GC__scopeRootVarsStackItem, %struct.PS_GC__scopeRootVarsStackItem* %6, i64 0, i32 1
  store %struct.PS_GC__scopeRootVarsStackItem* %11, %struct.PS_GC__scopeRootVarsStackItem** %12, align 8, !tbaa !11
  %13 = bitcast %struct.PS_GC__scopeRootVarsStack* %0 to i8**
  store i8* %5, i8** %13, align 8, !tbaa !4
  br label %14

14:                                               ; preds = %8, %4, %2
  %15 = phi i32 [ 0, %2 ], [ 1, %8 ], [ 0, %4 ]
  ret i32 %15
}

; Function Attrs: nofree nounwind uwtable
define dso_local i32 @PS_GC__insertItem(%struct.PS_GC__hashset* nocapture noundef readonly %0, %struct.PS_GC__object* noundef %1) local_unnamed_addr #7 {
  %3 = getelementptr inbounds %struct.PS_GC__object, %struct.PS_GC__object* %1, i64 0, i32 0
  %4 = load i8*, i8** %3, align 8, !tbaa !22
  %5 = ptrtoint i8* %4 to i64
  %6 = lshr i64 %5, 5
  %7 = getelementptr inbounds %struct.PS_GC__hashset, %struct.PS_GC__hashset* %0, i64 0, i32 2
  %8 = load i64, i64* %7, align 8, !tbaa !17
  %9 = and i64 %6, %8
  %10 = getelementptr inbounds %struct.PS_GC__hashset, %struct.PS_GC__hashset* %0, i64 0, i32 0
  %11 = load %struct.PS_GC__hashset_bucket**, %struct.PS_GC__hashset_bucket*** %10, align 8, !tbaa !18
  %12 = shl i64 %9, 32
  %13 = ashr exact i64 %12, 32
  %14 = getelementptr inbounds %struct.PS_GC__hashset_bucket*, %struct.PS_GC__hashset_bucket** %11, i64 %13
  %15 = load %struct.PS_GC__hashset_bucket*, %struct.PS_GC__hashset_bucket** %14, align 8, !tbaa !31
  %16 = icmp eq %struct.PS_GC__hashset_bucket* %15, null
  br i1 %16, label %28, label %21

17:                                               ; preds = %21
  %18 = getelementptr inbounds %struct.PS_GC__hashset_bucket, %struct.PS_GC__hashset_bucket* %22, i64 0, i32 1
  %19 = load %struct.PS_GC__hashset_bucket*, %struct.PS_GC__hashset_bucket** %18, align 8, !tbaa !31
  %20 = icmp eq %struct.PS_GC__hashset_bucket* %19, null
  br i1 %20, label %28, label %21, !llvm.loop !33

21:                                               ; preds = %2, %17
  %22 = phi %struct.PS_GC__hashset_bucket* [ %19, %17 ], [ %15, %2 ]
  %23 = getelementptr inbounds %struct.PS_GC__hashset_bucket, %struct.PS_GC__hashset_bucket* %22, i64 0, i32 0
  %24 = load %struct.PS_GC__object*, %struct.PS_GC__object** %23, align 8, !tbaa !21
  %25 = getelementptr inbounds %struct.PS_GC__object, %struct.PS_GC__object* %24, i64 0, i32 0
  %26 = load i8*, i8** %25, align 8, !tbaa !22
  %27 = icmp eq i8* %26, %4
  br i1 %27, label %37, label %17

28:                                               ; preds = %17, %2
  %29 = tail call noalias dereferenceable_or_null(16) i8* @malloc(i64 noundef 16) #10
  %30 = bitcast i8* %29 to %struct.PS_GC__hashset_bucket*
  %31 = icmp eq i8* %29, null
  br i1 %31, label %37, label %32

32:                                               ; preds = %28
  %33 = getelementptr inbounds %struct.PS_GC__hashset_bucket, %struct.PS_GC__hashset_bucket* %30, i64 0, i32 1
  %34 = getelementptr inbounds %struct.PS_GC__hashset_bucket, %struct.PS_GC__hashset_bucket* %30, i64 0, i32 0
  store %struct.PS_GC__object* %1, %struct.PS_GC__object** %34, align 8, !tbaa !21
  %35 = load %struct.PS_GC__hashset_bucket*, %struct.PS_GC__hashset_bucket** %14, align 8, !tbaa !31
  store %struct.PS_GC__hashset_bucket* %35, %struct.PS_GC__hashset_bucket** %33, align 8, !tbaa !19
  %36 = bitcast %struct.PS_GC__hashset_bucket** %14 to i8**
  store i8* %29, i8** %36, align 8, !tbaa !31
  br label %37

37:                                               ; preds = %21, %28, %32
  %38 = phi i32 [ 1, %32 ], [ -1, %28 ], [ 0, %21 ]
  ret i32 %38
}

; Function Attrs: nofree norecurse nosync nounwind readonly uwtable
define dso_local %struct.PS_GC__object* @PS_GC__getItem(%struct.PS_GC__hashset* nocapture noundef readonly %0, i8* noundef %1) local_unnamed_addr #8 {
  %3 = icmp eq i8* %1, null
  br i1 %3, label %28, label %4

4:                                                ; preds = %2
  %5 = ptrtoint i8* %1 to i64
  %6 = lshr i64 %5, 5
  %7 = getelementptr inbounds %struct.PS_GC__hashset, %struct.PS_GC__hashset* %0, i64 0, i32 2
  %8 = load i64, i64* %7, align 8, !tbaa !17
  %9 = and i64 %8, %6
  %10 = getelementptr inbounds %struct.PS_GC__hashset, %struct.PS_GC__hashset* %0, i64 0, i32 0
  %11 = load %struct.PS_GC__hashset_bucket**, %struct.PS_GC__hashset_bucket*** %10, align 8, !tbaa !18
  %12 = shl i64 %9, 32
  %13 = ashr exact i64 %12, 32
  %14 = getelementptr inbounds %struct.PS_GC__hashset_bucket*, %struct.PS_GC__hashset_bucket** %11, i64 %13
  %15 = load %struct.PS_GC__hashset_bucket*, %struct.PS_GC__hashset_bucket** %14, align 8, !tbaa !31
  %16 = icmp eq %struct.PS_GC__hashset_bucket* %15, null
  br i1 %16, label %28, label %21

17:                                               ; preds = %21
  %18 = getelementptr inbounds %struct.PS_GC__hashset_bucket, %struct.PS_GC__hashset_bucket* %22, i64 0, i32 1
  %19 = load %struct.PS_GC__hashset_bucket*, %struct.PS_GC__hashset_bucket** %18, align 8, !tbaa !31
  %20 = icmp eq %struct.PS_GC__hashset_bucket* %19, null
  br i1 %20, label %28, label %21, !llvm.loop !34

21:                                               ; preds = %4, %17
  %22 = phi %struct.PS_GC__hashset_bucket* [ %19, %17 ], [ %15, %4 ]
  %23 = getelementptr inbounds %struct.PS_GC__hashset_bucket, %struct.PS_GC__hashset_bucket* %22, i64 0, i32 0
  %24 = load %struct.PS_GC__object*, %struct.PS_GC__object** %23, align 8, !tbaa !21
  %25 = getelementptr inbounds %struct.PS_GC__object, %struct.PS_GC__object* %24, i64 0, i32 0
  %26 = load i8*, i8** %25, align 8, !tbaa !22
  %27 = icmp eq i8* %26, %1
  br i1 %27, label %28, label %17

28:                                               ; preds = %17, %21, %4, %2
  %29 = phi %struct.PS_GC__object* [ null, %2 ], [ null, %4 ], [ null, %17 ], [ %24, %21 ]
  ret %struct.PS_GC__object* %29
}

; Function Attrs: nounwind uwtable
define dso_local i32 @PS_GC__removeItem(%struct.PS_GC__hashset* nocapture noundef readonly %0, %struct.PS_GC__object* nocapture noundef readonly %1) local_unnamed_addr #2 {
  %3 = getelementptr inbounds %struct.PS_GC__object, %struct.PS_GC__object* %1, i64 0, i32 0
  %4 = load i8*, i8** %3, align 8, !tbaa !22
  %5 = ptrtoint i8* %4 to i64
  %6 = lshr i64 %5, 5
  %7 = getelementptr inbounds %struct.PS_GC__hashset, %struct.PS_GC__hashset* %0, i64 0, i32 2
  %8 = load i64, i64* %7, align 8, !tbaa !17
  %9 = and i64 %6, %8
  %10 = getelementptr inbounds %struct.PS_GC__hashset, %struct.PS_GC__hashset* %0, i64 0, i32 0
  %11 = load %struct.PS_GC__hashset_bucket**, %struct.PS_GC__hashset_bucket*** %10, align 8, !tbaa !18
  %12 = shl i64 %9, 32
  %13 = ashr exact i64 %12, 32
  %14 = getelementptr inbounds %struct.PS_GC__hashset_bucket*, %struct.PS_GC__hashset_bucket** %11, i64 %13
  %15 = load %struct.PS_GC__hashset_bucket*, %struct.PS_GC__hashset_bucket** %14, align 8, !tbaa !31
  %16 = icmp eq %struct.PS_GC__hashset_bucket* %15, null
  br i1 %16, label %42, label %17

17:                                               ; preds = %2
  %18 = getelementptr inbounds %struct.PS_GC__hashset_bucket, %struct.PS_GC__hashset_bucket* %15, i64 0, i32 0
  %19 = load %struct.PS_GC__object*, %struct.PS_GC__object** %18, align 8, !tbaa !21
  %20 = getelementptr inbounds %struct.PS_GC__object, %struct.PS_GC__object* %19, i64 0, i32 0
  %21 = load i8*, i8** %20, align 8, !tbaa !22
  %22 = icmp eq i8* %21, %4
  br i1 %22, label %36, label %23

23:                                               ; preds = %17, %28
  %24 = phi %struct.PS_GC__hashset_bucket* [ %26, %28 ], [ %15, %17 ]
  %25 = getelementptr inbounds %struct.PS_GC__hashset_bucket, %struct.PS_GC__hashset_bucket* %24, i64 0, i32 1
  %26 = load %struct.PS_GC__hashset_bucket*, %struct.PS_GC__hashset_bucket** %25, align 8, !tbaa !19
  %27 = icmp eq %struct.PS_GC__hashset_bucket* %26, null
  br i1 %27, label %42, label %28

28:                                               ; preds = %23
  %29 = getelementptr inbounds %struct.PS_GC__hashset_bucket, %struct.PS_GC__hashset_bucket* %26, i64 0, i32 0
  %30 = load %struct.PS_GC__object*, %struct.PS_GC__object** %29, align 8, !tbaa !21
  %31 = getelementptr inbounds %struct.PS_GC__object, %struct.PS_GC__object* %30, i64 0, i32 0
  %32 = load i8*, i8** %31, align 8, !tbaa !22
  %33 = icmp eq i8* %32, %4
  br i1 %33, label %34, label %23, !llvm.loop !35

34:                                               ; preds = %28
  %35 = getelementptr inbounds %struct.PS_GC__hashset_bucket, %struct.PS_GC__hashset_bucket* %24, i64 0, i32 1
  br label %36

36:                                               ; preds = %17, %34
  %37 = phi %struct.PS_GC__hashset_bucket* [ %26, %34 ], [ %15, %17 ]
  %38 = phi %struct.PS_GC__hashset_bucket** [ %35, %34 ], [ %14, %17 ]
  %39 = getelementptr inbounds %struct.PS_GC__hashset_bucket, %struct.PS_GC__hashset_bucket* %37, i64 0, i32 1
  %40 = load %struct.PS_GC__hashset_bucket*, %struct.PS_GC__hashset_bucket** %39, align 8, !tbaa !19
  store %struct.PS_GC__hashset_bucket* %40, %struct.PS_GC__hashset_bucket** %38, align 8, !tbaa !31
  %41 = bitcast %struct.PS_GC__hashset_bucket* %37 to i8*
  tail call void @free(i8* noundef %41) #10
  br label %42

42:                                               ; preds = %23, %36, %2
  %43 = phi i32 [ 0, %2 ], [ 1, %36 ], [ 0, %23 ]
  ret i32 %43
}

; Function Attrs: argmemonly nofree nounwind willreturn writeonly
declare void @llvm.memset.p0i8.i64(i8* nocapture writeonly, i8, i64, i1 immarg) #9

attributes #0 = { mustprogress nofree nounwind uwtable willreturn "frame-pointer"="none" "min-legal-vector-width"="0" "no-trapping-math"="true" "stack-protector-buffer-size"="8" "target-cpu"="x86-64" "target-features"="+cx8,+fxsr,+mmx,+sse,+sse2,+x87" "tune-cpu"="generic" }
attributes #1 = { inaccessiblememonly mustprogress nofree nounwind willreturn "frame-pointer"="none" "no-trapping-math"="true" "stack-protector-buffer-size"="8" "target-cpu"="x86-64" "target-features"="+cx8,+fxsr,+mmx,+sse,+sse2,+x87" "tune-cpu"="generic" }
attributes #2 = { nounwind uwtable "frame-pointer"="none" "min-legal-vector-width"="0" "no-trapping-math"="true" "stack-protector-buffer-size"="8" "target-cpu"="x86-64" "target-features"="+cx8,+fxsr,+mmx,+sse,+sse2,+x87" "tune-cpu"="generic" }
attributes #3 = { inaccessiblemem_or_argmemonly mustprogress nounwind willreturn "frame-pointer"="none" "no-trapping-math"="true" "stack-protector-buffer-size"="8" "target-cpu"="x86-64" "target-features"="+cx8,+fxsr,+mmx,+sse,+sse2,+x87" "tune-cpu"="generic" }
attributes #4 = { mustprogress nofree norecurse nosync nounwind uwtable willreturn writeonly "frame-pointer"="none" "min-legal-vector-width"="0" "no-trapping-math"="true" "stack-protector-buffer-size"="8" "target-cpu"="x86-64" "target-features"="+cx8,+fxsr,+mmx,+sse,+sse2,+x87" "tune-cpu"="generic" }
attributes #5 = { mustprogress nounwind uwtable willreturn "frame-pointer"="none" "min-legal-vector-width"="0" "no-trapping-math"="true" "stack-protector-buffer-size"="8" "target-cpu"="x86-64" "target-features"="+cx8,+fxsr,+mmx,+sse,+sse2,+x87" "tune-cpu"="generic" }
attributes #6 = { mustprogress nofree norecurse nosync nounwind readonly uwtable willreturn "frame-pointer"="none" "min-legal-vector-width"="0" "no-trapping-math"="true" "stack-protector-buffer-size"="8" "target-cpu"="x86-64" "target-features"="+cx8,+fxsr,+mmx,+sse,+sse2,+x87" "tune-cpu"="generic" }
attributes #7 = { nofree nounwind uwtable "frame-pointer"="none" "min-legal-vector-width"="0" "no-trapping-math"="true" "stack-protector-buffer-size"="8" "target-cpu"="x86-64" "target-features"="+cx8,+fxsr,+mmx,+sse,+sse2,+x87" "tune-cpu"="generic" }
attributes #8 = { nofree norecurse nosync nounwind readonly uwtable "frame-pointer"="none" "min-legal-vector-width"="0" "no-trapping-math"="true" "stack-protector-buffer-size"="8" "target-cpu"="x86-64" "target-features"="+cx8,+fxsr,+mmx,+sse,+sse2,+x87" "tune-cpu"="generic" }
attributes #9 = { argmemonly nofree nounwind willreturn writeonly }
attributes #10 = { nounwind }

!llvm.module.flags = !{!0, !1, !2}
!llvm.ident = !{!3}

!0 = !{i32 1, !"wchar_size", i32 2}
!1 = !{i32 7, !"PIC Level", i32 2}
!2 = !{i32 7, !"uwtable", i32 1}
!3 = !{!"clang version 14.0.6"}
!4 = !{!5, !6, i64 0}
!5 = !{!"PS_GC__scopeRootVarsStack", !6, i64 0}
!6 = !{!"any pointer", !7, i64 0}
!7 = !{!"omnipotent char", !8, i64 0}
!8 = !{!"Simple C/C++ TBAA"}
!9 = !{!10, !6, i64 0}
!10 = !{!"PS_GC__scopeRootVarsStackItem", !6, i64 0, !6, i64 8}
!11 = !{!10, !6, i64 8}
!12 = distinct !{!12, !13}
!13 = !{!"llvm.loop.mustprogress"}
!14 = !{!15, !16, i64 8}
!15 = !{!"PS_GC__hashset", !6, i64 0, !16, i64 8, !16, i64 16}
!16 = !{!"long long", !7, i64 0}
!17 = !{!15, !16, i64 16}
!18 = !{!15, !6, i64 0}
!19 = !{!20, !6, i64 8}
!20 = !{!"PS_GC__hashset_bucket", !6, i64 0, !6, i64 8}
!21 = !{!20, !6, i64 0}
!22 = !{!23, !6, i64 0}
!23 = !{!"PS_GC__object", !6, i64 0, !7, i64 8, !6, i64 16, !16, i64 24}
!24 = !{!23, !7, i64 8}
!25 = !{!23, !6, i64 16}
!26 = !{!23, !16, i64 24}
!27 = !{!28, !16, i64 0}
!28 = !{!"PS_GC__rootVarList", !16, i64 0, !6, i64 8}
!29 = !{!28, !6, i64 8}
!30 = distinct !{!30, !13}
!31 = !{!6, !6, i64 0}
!32 = distinct !{!32, !13}
!33 = distinct !{!33, !13}
!34 = distinct !{!34, !13}
!35 = distinct !{!35, !13}
