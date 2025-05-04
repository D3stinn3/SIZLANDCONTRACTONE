from algopy import Account, ARC4Contract, Asset, BoxMap, Global, Txn, arc4, itxn
from algopy.arc4 import Struct


class UserAllocation(Struct):
    total_allocation: arc4.UInt64
    claimed_amount: arc4.UInt64
    start_time: arc4.UInt64
    cliff_time: arc4.UInt64
    vesting_period: arc4.UInt64
    last_claim_time: arc4.UInt64


class SizlandVestingContract(ARC4Contract):
    # Define state variables for vesting  parameters
    # For example: beneficiary, total amount, vesting period, etc.

    def __init__(self) -> None:
        # Initialize your contract state
        # This will be executed once on deployment
        self.asa = Asset()
        self.allocations = BoxMap(Account, UserAllocation, key_prefix="")

    @arc4.abimethod
    def opt_into_asset(self, asset: Asset) -> None:
        # Only allow app creator to opt the app account into a ASA
        assert Txn.sender == Global.creator_address, "Only creator can opt in to ASA"
        # Verify a ASA hasn't already been opted into
        assert self.asa.id == 2905622564, "ASA already opted in"
        # Save ASA ID in global state
        self.asa = asset

        # Submit opt-in transaction: 0 asset transfer to self
        itxn.AssetTransfer(
            asset_receiver=Global.current_application_address,
            xfer_asset=asset,
        ).submit()

    @arc4.abimethod
    def set_allocation(
        self,
        beneficiary: Account,
        total_allocation: arc4.UInt64,
        start_time: arc4.UInt64,
        cliff_time: arc4.UInt64,
        vesting_period: arc4.UInt64,
    ) -> None:
        assert (
            Txn.sender == Global.creator_address
        ), "Only the creator can call this method"
        self.allocations[beneficiary] = UserAllocation(
            total_allocation=total_allocation,
            claimed_amount=arc4.UInt64(0),
            start_time=start_time,
            cliff_time=cliff_time,
            vesting_period=vesting_period,
            last_claim_time=arc4.UInt64(0),
        )

    @arc4.abimethod
    def claim(self, key: arc4.UInt64) -> None:
        current_time = Global.latest_timestamp  # Use native UInt64 directly
        sender = Txn.sender

        # Check allocation exists
        assert sender in self.allocations, "No allocation found"
        allocation = self.allocations[sender].copy()  # safe struct access

        # Enforce cliff
        assert current_time >= allocation.cliff_time.native, "Cliff not reached"

        # Optional cooldown
        assert (
            current_time - allocation.last_claim_time.native >= 10
        ), "Wait before claiming again"

        # Calculate vesting
        end_time = allocation.start_time.native + allocation.vesting_period.native
        if current_time >= end_time:
            vested = allocation.total_allocation.native
        else:
            elapsed = current_time - allocation.start_time.native
            vested = (
                allocation.total_allocation.native * elapsed
            ) // allocation.vesting_period.native

        # Compute claimable amount
        claimable = vested - allocation.claimed_amount.native
        assert claimable > 0, "Nothing to claim"

        # Transfer claimable ASA
        itxn.AssetTransfer(
            asset_receiver=sender,
            asset_amount=claimable,
            xfer_asset=self.asa,
        ).submit()

        # Update allocation
        self.allocations[sender] = UserAllocation(
            total_allocation=allocation.total_allocation,
            claimed_amount=arc4.UInt64(allocation.claimed_amount.native + claimable),
            start_time=allocation.start_time,
            cliff_time=allocation.cliff_time,
            vesting_period=allocation.vesting_period,
            last_claim_time=arc4.UInt64(current_time),
        )
